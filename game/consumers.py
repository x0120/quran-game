import json
import math

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import AnswerChoice, GameSession, Player, PlayerAnswer, Question

REVEAL_SECONDS = 10
POINTS_PER_CORRECT_ANSWER = 1


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_code = self.scope['url_route']['kwargs']['session_code']
        self.room_group_name = f'game_{self.session_code}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'student_join':
            player_id = data.get('player_id')
            await self.set_player_connected(player_id, True)
            await self.broadcast_state()

        elif action == 'start_game':
            await self.update_session_state('active', 0)
            await self.broadcast_state()

        elif action == 'reveal_question':
            current_index = await self.get_current_question_index()
            await self.update_session_state('revealed', current_index)
            await self.broadcast_state()

        elif action == 'submit_answer':
            player_id = data.get('player_id')
            choice_id = data.get('choice_id')
            time_taken = data.get('time_taken', 0.0)
            await self.save_player_answer(player_id, choice_id, time_taken)
            if await self.should_reveal_current_question():
                current_index = await self.get_current_question_index()
                await self.update_session_state('revealed', current_index)
            await self.broadcast_state()

        elif action == 'clear_answer':
            player_id = data.get('player_id')
            await self.clear_player_answer(player_id)
            await self.broadcast_state()

        elif action == 'leave_game':
            player_id = data.get('player_id')
            await self.set_player_connected(player_id, False)
            if await self.should_reveal_current_question():
                current_index = await self.get_current_question_index()
                await self.update_session_state('revealed', current_index)
            await self.broadcast_state()

        elif action == 'cancel_game':
            current_index = await self.get_current_question_index()
            await self.update_session_state('cancelled', current_index)
            await self.broadcast_state()

        elif action == 'show_results':
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "game_message", "message": {"type": "show_results"}}
            )

        elif action == 'request_state':
            await self.send_current_state()

    async def game_message(self, event):
        message = event['message']
        if message.get('type') == 'state_update':
            await self.send_current_state()
            return
        await self.send(text_data=json.dumps(message))

    async def broadcast_state(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "game_message", "message": {"type": "state_update"}}
        )

    async def send_current_state(self):
        state = await self.get_game_state()
        await self.send(text_data=json.dumps({"type": "state_update", "state": state}))

    @database_sync_to_async
    def get_game_state(self):
        try:
            session = GameSession.objects.get(code=self.session_code)
            self._sync_session_timer_state(session)
            session.refresh_from_db()

            viewer_player = self._get_viewer_player(session)
            players = list(session.players.filter(is_connected=True).values('id', 'name', 'score'))
            players.sort(key=lambda x: x['score'], reverse=True)

            state = {
                'state': session.state,
                'timer': session.timer_seconds,
                'remaining_seconds': session.timer_seconds,
                'reveal_seconds': REVEAL_SECONDS,
                'reveal_setting': session.reveal_answer_setting,
                'players': players,
                'current_question': None,
                'current_question_number': 0,
                'total_questions': len(self._get_ordered_questions(session)),
                'answers_count': 0,
                'viewer_role': self._get_viewer_role(session, viewer_player),
                'my_answer': None,
            }

            if session.state in ['active', 'revealed']:
                questions = self._get_ordered_questions(session)
                if session.current_question_index < len(questions):
                    question = questions[session.current_question_index]
                    state['current_question_number'] = session.current_question_index + 1
                    state['current_question'] = {
                        'id': question.id,
                        'text': question.text,
                        'choices': list(question.choices.values('id', 'text', 'is_correct'))
                    }
                    state['answers_count'] = (
                        PlayerAnswer.objects
                        .filter(
                            player__session=session,
                            player__is_connected=True,
                            question=question
                        )
                        .count()
                    )
                    if session.state == 'active':
                        state['remaining_seconds'] = self._get_remaining_seconds(session)
                    else:
                        state['remaining_seconds'] = self._get_reveal_remaining_seconds(session)

                    if viewer_player:
                        my_answer = (
                            PlayerAnswer.objects
                            .select_related('selected_choice')
                            .filter(player=viewer_player, question=question)
                            .first()
                        )
                        if my_answer:
                            state['my_answer'] = {
                                'choice_id': my_answer.selected_choice_id,
                                'choice_text': my_answer.selected_choice.text,
                                'is_correct': my_answer.is_correct,
                            }

            return state
        except GameSession.DoesNotExist:
            return {}

    @database_sync_to_async
    def set_player_connected(self, player_id, is_connected):
        Player.objects.filter(id=player_id, session__code=self.session_code).update(is_connected=is_connected)

    @database_sync_to_async
    def update_session_state(self, new_state, new_index):
        session = GameSession.objects.get(code=self.session_code)
        session.ensure_question_order()
        session.state = new_state
        session.current_question_index = new_index
        update_fields = ['state', 'current_question_index']

        if new_state == 'active':
            now = timezone.now()
            session.question_started_at = now
            session.revealed_at = None
            update_fields.append('question_started_at')
            update_fields.append('revealed_at')
            if not session.started_at:
                session.started_at = now
                update_fields.append('started_at')
        elif new_state == 'revealed':
            session.question_started_at = None
            session.revealed_at = timezone.now()
            update_fields.append('question_started_at')
            update_fields.append('revealed_at')
        else:
            session.question_started_at = None
            session.revealed_at = None
            update_fields.append('question_started_at')
            update_fields.append('revealed_at')

        session.save(update_fields=update_fields)

    @database_sync_to_async
    def get_current_question_index(self):
        return GameSession.objects.get(code=self.session_code).current_question_index

    @database_sync_to_async
    def get_total_questions(self):
        session = GameSession.objects.get(code=self.session_code)
        return len(self._get_ordered_questions(session))

    @database_sync_to_async
    def save_player_answer(self, player_id, choice_id, time_taken):
        self.save_player_answer_sync(player_id, choice_id, time_taken)

    def save_player_answer_sync(self, player_id, choice_id, time_taken):
        if not player_id or not choice_id:
            return

        player = Player.objects.get(id=player_id)
        if player.session.code != self.session_code or not player.is_connected:
            return

        session = player.session
        self._sync_session_timer_state(session)
        session.refresh_from_db()
        if session.state != 'active':
            return

        choice = AnswerChoice.objects.get(id=choice_id)
        question = choice.question
        if question.id not in session.ensure_question_order(save=False):
            return

        existing_answer = PlayerAnswer.objects.filter(player=player, question=question).first()
        previous_correct = existing_answer.is_correct if existing_answer else False

        if existing_answer:
            existing_answer.selected_choice = choice
            existing_answer.is_correct = choice.is_correct
            existing_answer.time_taken = time_taken
            existing_answer.save(update_fields=['selected_choice', 'is_correct', 'time_taken'])
        else:
            PlayerAnswer.objects.create(
                player=player,
                question=question,
                selected_choice=choice,
                is_correct=choice.is_correct,
                time_taken=time_taken
            )

        if previous_correct != choice.is_correct:
            player.score += POINTS_PER_CORRECT_ANSWER if choice.is_correct else -POINTS_PER_CORRECT_ANSWER
            player.save(update_fields=['score'])

    @database_sync_to_async
    def clear_player_answer(self, player_id):
        self.clear_player_answer_sync(player_id)

    def clear_player_answer_sync(self, player_id):
        if not player_id:
            return

        player = Player.objects.get(id=player_id)
        if player.session.code != self.session_code or not player.is_connected:
            return

        session = player.session
        self._sync_session_timer_state(session)
        session.refresh_from_db()
        if session.state != 'active':
            return

        questions = self._get_ordered_questions(session)
        if session.current_question_index >= len(questions):
            return

        current_question = questions[session.current_question_index]
        existing_answer = PlayerAnswer.objects.filter(player=player, question=current_question).first()
        if not existing_answer:
            return

        if existing_answer.is_correct:
            player.score -= POINTS_PER_CORRECT_ANSWER
            player.save(update_fields=['score'])

        existing_answer.delete()

    @database_sync_to_async
    def should_reveal_current_question(self):
        return self.should_reveal_current_question_sync()

    def should_reveal_current_question_sync(self):
        session = GameSession.objects.get(code=self.session_code)
        self._sync_session_timer_state(session)
        session.refresh_from_db()
        if session.state != 'active':
            return False

        questions = self._get_ordered_questions(session)
        if session.current_question_index >= len(questions):
            return False

        current_question = questions[session.current_question_index]
        connected_player_ids = list(
            session.players.filter(is_connected=True).values_list('id', flat=True)
        )
        if not connected_player_ids:
            return False

        answered_count = (
            PlayerAnswer.objects
            .filter(player_id__in=connected_player_ids, question=current_question)
            .values('player_id')
            .distinct()
            .count()
        )
        return answered_count >= len(connected_player_ids)

    def _sync_session_timer_state(self, session):
        if session.state == 'active' and session.question_started_at:
            if self._get_remaining_seconds(session) > 0:
                return

            session.state = 'revealed'
            session.question_started_at = None
            session.revealed_at = timezone.now()
            session.save(update_fields=['state', 'question_started_at', 'revealed_at'])
            return

        if session.state == 'revealed' and session.revealed_at:
            if self._get_reveal_remaining_seconds(session) > 0:
                return

            questions = self._get_ordered_questions(session)
            next_index = session.current_question_index + 1
            if next_index < len(questions):
                session.state = 'active'
                session.current_question_index = next_index
                session.question_started_at = timezone.now()
                session.revealed_at = None
                session.save(update_fields=['state', 'current_question_index', 'question_started_at', 'revealed_at'])
            else:
                session.state = 'finished'
                session.question_started_at = None
                session.revealed_at = None
                session.save(update_fields=['state', 'question_started_at', 'revealed_at'])

    def _get_remaining_seconds(self, session):
        if not session.question_started_at:
            return session.timer_seconds

        elapsed_seconds = (timezone.now() - session.question_started_at).total_seconds()
        return max(0, math.ceil(session.timer_seconds - elapsed_seconds))

    def _get_reveal_remaining_seconds(self, session):
        if not session.revealed_at:
            return REVEAL_SECONDS

        elapsed_seconds = (timezone.now() - session.revealed_at).total_seconds()
        return max(0, math.ceil(REVEAL_SECONDS - elapsed_seconds))

    def _get_viewer_player(self, session):
        session_store = self.scope.get('session')
        if not session_store:
            return None

        player_id = session_store.get('player_id')
        if not player_id:
            return None

        return Player.objects.filter(id=player_id, session=session).first()

    def _get_viewer_role(self, session, viewer_player):
        if viewer_player:
            return 'player'

        session_store = self.scope.get('session')
        if session_store and session_store.session_key == session.teacher_session_key:
            return 'teacher'

        return 'guest'

    def _get_ordered_questions(self, session):
        ordered_ids = session.ensure_question_order()
        questions_by_id = Question.objects.in_bulk(ordered_ids)
        return [questions_by_id[question_id] for question_id in ordered_ids if question_id in questions_by_id]
