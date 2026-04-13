import random

from django.db import models

class GameTemplate(models.Model):
    title = models.CharField(max_length=200)

    def __str__(self):
        return self.title

class Question(models.Model):
    game = models.ForeignKey(GameTemplate, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField(max_length=500)

    def __str__(self):
        return self.text

class AnswerChoice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=200)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Wrong'})"

class GameSession(models.Model):
    teacher_session_key = models.CharField(max_length=100)
    game = models.ForeignKey(GameTemplate, on_delete=models.CASCADE)
    code = models.CharField(max_length=4, unique=True)
    state = models.CharField(max_length=20, default='waiting') # waiting, active, revealed, finished, cancelled
    current_question_index = models.IntegerField(default=0)
    timer_seconds = models.IntegerField(default=30)
    reveal_answer_setting = models.CharField(max_length=20, default='after_question') # after_question, end_of_game
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    question_started_at = models.DateTimeField(null=True, blank=True)
    revealed_at = models.DateTimeField(null=True, blank=True)
    question_order = models.JSONField(default=list, blank=True)
    selected_letters = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Session {self.code}"

    def ensure_question_order(self, save=True):
        question_ids = self.get_filtered_question_ids()
        if set(self.question_order) == set(question_ids) and len(self.question_order) == len(question_ids):
            return self.question_order

        shuffled_ids = question_ids[:]
        random.shuffle(shuffled_ids)
        self.question_order = shuffled_ids
        if save:
            self.save(update_fields=['question_order'])
        return self.question_order

    def get_filtered_question_ids(self):
        questions = self.game.questions.order_by('id')
        if self.selected_letters:
            questions = questions.filter(
                choices__is_correct=True,
                choices__text__in=self.selected_letters
            ).distinct()
        return list(questions.values_list('id', flat=True))

class Player(models.Model):
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name='players')
    name = models.CharField(max_length=100)
    score = models.IntegerField(default=0)
    is_connected = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class PlayerAnswer(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(AnswerChoice, on_delete=models.CASCADE)
    is_correct = models.BooleanField()
    time_taken = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.player.name} -> {self.selected_choice.text}"
