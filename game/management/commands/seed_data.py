from django.core.management.base import BaseCommand
from game.models import GameTemplate, Question, AnswerChoice

class Command(BaseCommand):
    help = 'Seeds initial data for the Arabic rules game'

    def handle(self, *args, **kwargs):
        game, created = GameTemplate.objects.get_or_create(title="صفات الحروف الهجائية العربية")
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created GameTemplate'))
        else:
            self.stdout.write('GameTemplate already exists, resetting questions...')
            Question.objects.filter(game=game).delete()

        attributes_data = {
            "ء": "جهر، شدة، استفال، انفتاح، إصمات",
            "ا": "جهر، رخاوة، استفال، انفتاح، إصمات",
            "ب": "جهر، شدة، استفال، انفتاح، إذلاق، قلقلة",
            "ت": "همس، شدة، استفال، انفتاح، إصمات",
            "ث": "همس، رخاوة، استفال، انفتاح، إصمات",
            "ج": "جهر، شدة، استفال، انفتاح، إصمات، قلقلة",
            "ح": "همس، رخاوة، استفال، انفتاح، إصمات",
            "خ": "همس، رخاوة، استعلاء، انفتاح، إصمات",
            "د": "جهر، شدة، استفال، انفتاح، إصمات، قلقلة",
            "ذ": "جهر، رخاوة، استفال، انفتاح، إصمات",
            "ر": "جهر، بينية، استفال، انفتاح، إذلاق، انحراف، تكرير",
            "ز": "جهر، رخاوة، استفال، انفتاح، إصمات، صفير",
            "س": "همس، رخاوة، استفال، انفتاح، إصمات، صفير",
            "ش": "همس، رخاوة، استفال، انفتاح، إصمات، تفشي",
            "ص": "همس، رخاوة، استعلاء، إطباق، إصمات، صفير",
            "ض": "جهر، رخاوة، استعلاء، إطباق، إصمات، استطالة",
            "ط": "جهر، شدة، استعلاء، إطباق، إصمات، قلقلة",
            "ظ": "جهر، رخاوة، استعلاء، إطباق، إصمات",
            "ع": "جهر، بينية، استفال، انفتاح، إصمات",
            "غ": "جهر، رخاوة، استعلاء، انفتاح، إصمات",
            "ف": "همس، رخاوة، استفال، انفتاح، إذلاق",
            "ق": "جهر، شدة، استعلاء، انفتاح، إصمات، قلقلة",
            "ك": "همس، شدة، استفال، انفتاح، إصمات",
            "ل": "جهر، بينية، استفال، انفتاح، إذلاق، انحراف",
            "م": "جهر، بينية، استفال، انفتاح، إذلاق، غنة",
            "ن": "جهر، بينية، استفال، انفتاح، إذلاق، غنة",
            "ه": "همس، رخاوة، استفال، انفتاح، إصمات",
            "و": "جهر، رخاوة، لين، انفتاح، إصمات",
            "ي": "جهر، رخاوة، لين، انفتاح، إصمات"
        }

        all_letters = list(attributes_data.keys())

        for letter, attributes in attributes_data.items():
            q = Question.objects.create(game=game, text=attributes)
            for choice_letter in all_letters:
                AnswerChoice.objects.create(
                    question=q,
                    text=choice_letter,
                    is_correct=(choice_letter == letter)
                )

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {len(attributes_data)} questions!'))
