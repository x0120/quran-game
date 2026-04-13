from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .models import AnswerChoice, GameSession, GameTemplate, Player, Question
from .consumers import GameConsumer


class GameViewsTests(TestCase):
    def setUp(self):
        self.game = GameTemplate.objects.create(title='صفات الحروف')
        self.q1 = Question.objects.create(game=self.game, text='السؤال الأول')
        self.q2 = Question.objects.create(game=self.game, text='السؤال الثاني')
        self.q3 = Question.objects.create(game=self.game, text='السؤال الثالث')
        for question, letter in [(self.q1, 'ا'), (self.q2, 'ب'), (self.q3, 'ت')]:
            AnswerChoice.objects.create(question=question, text=letter, is_correct=True)
        self.session = GameSession.objects.create(
            teacher_session_key='teacher-key',
            game=self.game,
            code='123456',
        )

    def test_joining_reconnects_existing_player(self):
        player = Player.objects.create(
            session=self.session,
            name='أحمد',
            is_connected=False,
        )
        session = self.client.session
        session['player_id'] = player.id
        session.save()

        response = self.client.post(reverse('home'), {'code': self.session.code, 'name': player.name})

        player.refresh_from_db()
        self.assertRedirects(response, reverse('play_game', args=[self.session.code]))
        self.assertTrue(player.is_connected)
        self.assertEqual(self.client.session['player_id'], player.id)

    def test_joining_with_duplicate_name_in_same_room_shows_error(self):
        Player.objects.create(session=self.session, name='أحمد', is_connected=True)

        response = self.client.post(reverse('home'), {'code': self.session.code, 'name': 'أحمد'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'هذا الاسم مستخدم بالفعل في هذه الغرفة. اختر اسماً آخر.')
        self.assertEqual(Player.objects.filter(session=self.session, name='أحمد').count(), 1)

    def test_cancelled_session_cannot_be_joined(self):
        self.session.state = 'cancelled'
        self.session.save(update_fields=['state'])

        response = self.client.post(reverse('home'), {'code': self.session.code, 'name': 'سارة'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Player.objects.filter(session=self.session, name='سارة').exists())

    def test_exit_game_marks_player_disconnected_and_clears_session(self):
        player = Player.objects.create(session=self.session, name='ليان')
        session = self.client.session
        session['player_id'] = player.id
        session.save()

        response = self.client.get(reverse('exit_game', args=[self.session.code]))

        player.refresh_from_db()
        self.assertRedirects(response, reverse('home'))
        self.assertFalse(player.is_connected)
        self.assertNotIn('player_id', self.client.session)

    def test_question_order_is_shuffled_once_per_session(self):
        with patch('game.models.random.shuffle') as mocked_shuffle:
            def reverse_order(items):
                items.reverse()

            mocked_shuffle.side_effect = reverse_order
            first_order = self.session.ensure_question_order()
            second_order = self.session.ensure_question_order()

        self.assertEqual(first_order, [self.q3.id, self.q2.id, self.q1.id])
        self.assertEqual(second_order, first_order)

    def test_question_order_respects_selected_letters(self):
        self.session.selected_letters = ['ا', 'ت']
        self.session.save(update_fields=['selected_letters'])

        with patch('game.models.random.shuffle') as mocked_shuffle:
            mocked_shuffle.side_effect = lambda items: items.reverse()
            order = self.session.ensure_question_order()

        self.assertEqual(order, [self.q3.id, self.q1.id])

    def test_host_setup_can_create_session_for_specific_letters(self):
        session = self.client.session
        session.create()
        session.save()

        response = self.client.post(reverse('host_setup'), {
            'timer': 30,
            'reveal_setting': 'after_question',
            'letter_mode': 'specific',
            'selected_letters': ['ب', 'ت'],
        })

        created_session = GameSession.objects.exclude(id=self.session.id).get()
        self.assertRedirects(response, reverse('host_dashboard', args=[created_session.code]))
        self.assertEqual(created_session.selected_letters, ['ب', 'ت'])
        self.assertEqual(len(created_session.code), 4)

    def test_student_can_change_answer_before_reveal(self):
        player = Player.objects.create(session=self.session, name='نور')
        wrong_choice = AnswerChoice.objects.create(question=self.q1, text='ز', is_correct=False)
        correct_choice = self.q1.choices.get(is_correct=True)
        self.session.question_order = [self.q1.id]
        self.session.selected_letters = ['ا']
        self.session.state = 'active'
        self.session.save(update_fields=['question_order', 'selected_letters', 'state'])

        consumer = GameConsumer()
        consumer.session_code = self.session.code

        consumer.save_player_answer_sync(player.id, wrong_choice.id, 2.0)
        player.refresh_from_db()
        answer = player.answers.get(question=self.q1)
        self.assertEqual(answer.selected_choice_id, wrong_choice.id)
        self.assertEqual(player.score, 0)

        consumer.save_player_answer_sync(player.id, correct_choice.id, 4.0)
        player.refresh_from_db()
        answer.refresh_from_db()
        self.assertEqual(answer.selected_choice_id, correct_choice.id)
        self.assertTrue(answer.is_correct)
        self.assertEqual(player.score, 100)

    def test_clearing_answer_removes_saved_choice_and_score(self):
        player = Player.objects.create(session=self.session, name='سندس')
        correct_choice = self.q1.choices.get(is_correct=True)
        self.session.question_order = [self.q1.id]
        self.session.selected_letters = ['ا']
        self.session.state = 'active'
        self.session.save(update_fields=['question_order', 'selected_letters', 'state'])

        consumer = GameConsumer()
        consumer.session_code = self.session.code

        consumer.save_player_answer_sync(player.id, correct_choice.id, 2.0)
        consumer.clear_player_answer_sync(player.id)

        player.refresh_from_db()
        self.assertEqual(player.score, 0)
        self.assertFalse(player.answers.filter(question=self.q1).exists())

    def test_cleared_answer_no_longer_counts_as_answered(self):
        player_one = Player.objects.create(session=self.session, name='ريم')
        player_two = Player.objects.create(session=self.session, name='جود')
        correct_choice = self.q1.choices.get(is_correct=True)
        self.session.question_order = [self.q1.id]
        self.session.selected_letters = ['ا']
        self.session.state = 'active'
        self.session.save(update_fields=['question_order', 'selected_letters', 'state'])

        consumer = GameConsumer()
        consumer.session_code = self.session.code

        consumer.save_player_answer_sync(player_one.id, correct_choice.id, 1.0)
        consumer.save_player_answer_sync(player_two.id, correct_choice.id, 2.0)
        self.assertTrue(consumer.should_reveal_current_question_sync())

        consumer.clear_player_answer_sync(player_two.id)
        self.assertFalse(consumer.should_reveal_current_question_sync())

    def test_generate_session_code_returns_unique_four_digits(self):
        existing = GameSession.objects.create(
            teacher_session_key='other-key',
            game=self.game,
            code='1111',
        )
        self.assertEqual(existing.code, '1111')

        with patch('game.views.get_random_string', side_effect=['1111', '2222']):
            code = __import__('game.views', fromlist=['generate_session_code']).generate_session_code()

        self.assertEqual(code, '2222')
