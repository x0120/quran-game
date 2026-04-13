from django.shortcuts import render, redirect, get_object_or_404
from django.utils.crypto import get_random_string
from .models import GameTemplate, GameSession, Player


def get_available_letters(game_template):
    return list(
        game_template.questions
        .filter(choices__is_correct=True)
        .order_by('id')
        .values_list('choices__text', flat=True)
        .distinct()
    )


def generate_session_code():
    while True:
        code = get_random_string(4, allowed_chars='0123456789')
        if not GameSession.objects.filter(code=code).exists():
            return code

def home(request):
    error_message = None
    if request.method == 'POST':
        # Student joining
        code = request.POST.get('code', '').strip()
        name = request.POST.get('name', '').strip()
        if code and name:
            session = GameSession.objects.exclude(state__in=['finished', 'cancelled']).filter(code=code).first()
            if session:
                existing_player = Player.objects.filter(session=session, name=name).first()
                current_player_id = request.session.get('player_id')

                if existing_player:
                    if current_player_id == existing_player.id:
                        if not existing_player.is_connected:
                            existing_player.is_connected = True
                            existing_player.save(update_fields=['is_connected'])
                        return redirect('play_game', session_code=code)

                    error_message = 'هذا الاسم مستخدم بالفعل في هذه الغرفة. اختر اسماً آخر.'
                else:
                    player = Player.objects.create(session=session, name=name)
                    request.session['player_id'] = player.id
                    return redirect('play_game', session_code=code)
            else:
                error_message = 'رمز اللعبة غير صحيح أو أن هذه الغرفة لم تعد متاحة.'
    return render(request, 'game/home.html', {'error_message': error_message})

def host_setup(request):
    game_template = GameTemplate.objects.first()
    if not game_template:
        return render(request, 'game/error.html', {'message': 'لم يتم العثور على اللعبة - الرجاء إضافة الأسئلة أولاً'})

    available_letters = get_available_letters(game_template)
    
    if request.method == 'POST':
        timer = request.POST.get('timer', 30)
        reveal_setting = request.POST.get('reveal_setting', 'after_question')
        letter_mode = request.POST.get('letter_mode', 'all')
        selected_letters = request.POST.getlist('selected_letters')

        if letter_mode == 'specific':
            selected_letters = [letter for letter in available_letters if letter in selected_letters]
            if not selected_letters:
                return render(request, 'game/host_setup.html', {
                    'game': game_template,
                    'available_letters': available_letters,
                    'error_message': 'اختر حرفاً واحداً على الأقل لبدء اللعبة.',
                    'selected_letter_mode': 'specific',
                    'selected_letters': selected_letters,
                })
        else:
            selected_letters = available_letters[:]
        
        if not request.session.session_key:
            request.session.create()
            
        code = generate_session_code()
        game_session = GameSession.objects.create(
            teacher_session_key=request.session.session_key,
            game=game_template,
            code=code,
            timer_seconds=int(timer),
            reveal_answer_setting=reveal_setting,
            selected_letters=selected_letters,
        )
        return redirect('host_dashboard', session_code=code)
        
    return render(request, 'game/host_setup.html', {
        'game': game_template,
        'available_letters': available_letters,
        'selected_letter_mode': 'all',
        'selected_letters': [],
    })

def host_dashboard(request, session_code):
    session = get_object_or_404(GameSession, code=session_code)
    return render(request, 'game/host.html', {'session': session})

def play_game(request, session_code):
    session = get_object_or_404(GameSession, code=session_code)
    player_id = request.session.get('player_id')
    if not player_id:
        return redirect('home')
        
    player = get_object_or_404(Player, id=player_id, session=session)
    return render(request, 'game/play.html', {'session': session, 'player': player})

def exit_game(request, session_code):
    player_id = request.session.pop('player_id', None)
    if player_id:
        Player.objects.filter(id=player_id, session__code=session_code).update(is_connected=False)
    return redirect('home')
