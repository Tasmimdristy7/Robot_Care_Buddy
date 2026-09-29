from datetime import timedelta
from zoneinfo import ZoneInfo
from django.db import transaction
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.db.models import Q
from .models import Task, QuietHours
from .forms import TaskForm, QuietHoursForm


def serialize(task):
    return {'id':task.id, 'title':task.title, 'course':task.course, 'kind':task.kind,
            'due_at':task.due_at.isoformat(), 'completed':task.completed, 'reminder_hours':task.reminder_hours,
            'repeat_days':task.repeat_days, 'repeat_timezone':task.repeat_timezone,
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
        # Claim completion inside the same transaction as successor creation.
        # The permanent flag prevents duplicates after retries or reopening history.
        with transaction.atomic():
            claimed = Task.objects.filter(pk=pk, completed=False, recurrence_generated=False).update(
                completed=True, recurrence_generated=bool(task.repeat_days), snoozed_until=None)
            if claimed and task.repeat_days:
                next_due = task.due_at.astimezone(ZoneInfo(task.repeat_timezone)) + timedelta(days=task.repeat_days)
                Task.objects.create(title=task.title, course=task.course, kind=task.kind,
                    due_at=next_due, reminder_hours=task.reminder_hours,
                    repeat_days=task.repeat_days, repeat_timezone=task.repeat_timezone)
            Task.objects.filter(pk=pk).update(completed=True, snoozed_until=None)
        task.refresh_from_db()
        return JsonResponse(serialize(task))
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
    settings = QuietHours.objects.filter(pk=1).first()
    if settings and settings.is_active(now):
        return JsonResponse({'tasks':[], 'now':now.isoformat(), 'quiet':True})
    due = Task.objects.filter(completed=False).filter(Q(snoozed_until__isnull=True)|Q(snoozed_until__lte=now))
    return JsonResponse({'tasks':[serialize(task) for task in due if task.due_at <= now + timedelta(hours=task.reminder_hours)], 'now':now.isoformat(), 'quiet':False})

@require_GET
def fun_fact(request):
    import random
    from .facts import FACTS
    previous = request.GET.get('previous', '')
    choices = [(i, fact) for i, fact in enumerate(FACTS) if str(i) != previous]
    index, fact = random.choice(choices)
    return JsonResponse({'id':index, 'fact':fact})

@require_GET
def joke(request):
    import random
    from .facts import JOKES
    choices = [(i, text) for i, text in enumerate(JOKES) if str(i) != request.GET.get('previous', '')]
    index, text = random.choice(choices)
    return JsonResponse({'id':index, 'joke':text})


@require_http_methods(['GET', 'POST'])
def quiet_hours(request):
    settings = QuietHours.objects.filter(pk=1).first() or QuietHours(pk=1)
    if request.method == 'POST':
        form = QuietHoursForm(request.POST, instance=settings)
        if not form.is_valid():
            return JsonResponse({'errors':form.errors.get_json_data()}, status=400)
        settings = form.save()
    return JsonResponse({'enabled':settings.enabled, 'start':str(settings.start)[:5],
                         'end':str(settings.end)[:5], 'timezone':settings.timezone,
                         'saved':not settings._state.adding})
