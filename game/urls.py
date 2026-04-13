from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('host/', views.host_setup, name='host_setup'),
    path('host/<str:session_code>/', views.host_dashboard, name='host_dashboard'),
    path('play/<str:session_code>/', views.play_game, name='play_game'),
    path('play/<str:session_code>/exit/', views.exit_game, name='exit_game'),
]
