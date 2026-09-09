from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.db.models import Q
from .models import Task
from .forms import TaskForm


def serialize(task):
    return {'id':task.id, 'title':task.title, 'course':task.course, 'kind':task.kind,
            'due_at':task.due_at.isoformat(), 'completed':task.completed,
            'snoozed_until':task.snoozed_until.isoformat() if task.snoozed_until else None}

@ensure_csrf_cookie
@require_GET
def home(request):
    return render(request, 'planner/home.html')

@require_http_methods(['GET', 'POST'])
def tasks(request):
    if request.method == 'GET':
        return JsonResponse({'tasks':[serialize(task) for task in Task.objects.all()]})
    form = TaskForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors':form.errors.get_json_data()}, status=400)
    return JsonResponse(serialize(form.save()), status=201)

@require_POST
def task_action(request, pk):
    task = get_object_or_404(Task, pk=pk)
    action = request.POST.get('action')
    if action == 'delete':
        task.delete()
        return JsonResponse({'deleted':True})
    if action == 'edit':
        form = TaskForm(request.POST, instance=task)
        if not form.is_valid():
            return JsonResponse({'errors':form.errors.get_json_data()}, status=400)
        task = form.save(commit=False)
        task.snoozed_until = None
    elif action == 'complete':
        task.completed = True
        task.snoozed_until = None
    elif action == 'reopen':
        task.completed = False
    elif action == 'snooze':
        task.snoozed_until = timezone.now() + timedelta(minutes=15)
    else:
        return JsonResponse({'error':'Unknown action.'}, status=400)
    task.save()
    return JsonResponse(serialize(task))

@require_GET
def reminders(request):
    now = timezone.now()
    due = Task.objects.filter(completed=False, due_at__lte=now+timedelta(days=2)).filter(Q(snoozed_until__isnull=True)|Q(snoozed_until__lte=now))
    return JsonResponse({'tasks':[serialize(task) for task in due], 'now':now.isoformat()})
