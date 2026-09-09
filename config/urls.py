from django.urls import path
from planner import views
urlpatterns = [path('', views.home, name='home'), path('tasks/', views.tasks, name='tasks'), path('tasks/<int:pk>/', views.task_action, name='task_action'), path('reminders/', views.reminders, name='reminders')]
