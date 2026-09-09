from django.urls import path
from planner import views
urlpatterns = [path('joke/', views.joke, name='joke'), path('fun-fact/', views.fun_fact, name='fun_fact'), path('', views.home, name='home'), path('tasks/', views.tasks, name='tasks'), path('tasks/<int:pk>/', views.task_action, name='task_action'), path('reminders/', views.reminders, name='reminders')]
