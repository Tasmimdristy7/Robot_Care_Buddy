"""Pytest regression tests for task management and reminder eligibility."""
from datetime import datetime, timedelta, timezone as datetime_timezone

import pytest
from django.test import Client
from django.utils import timezone

from .facts import FACTS, JOKES
from .models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def task_data():
    return {
        'title': 'Study graphs',
        'course': 'CSCI 713',
        'kind': 'exam',
        'due_at': (timezone.now() + timedelta(hours=20)).isoformat(),
    }


@pytest.fixture
def fixed_now(monkeypatch):
    now = datetime(2026, 10, 8, 12, tzinfo=datetime_timezone.utc)
    monkeypatch.setattr('planner.views.timezone.now', lambda: now)
    return now


@pytest.fixture
def reminder_ids(client, fixed_now):
    def fetch():
        response = client.get('/reminders/')
        assert response.status_code == 200
        assert response.json()['now'] == fixed_now.isoformat()
        return [task['id'] for task in response.json()['tasks']]
    return fetch


def test_create_edit_complete_reopen_delete(client, task_data):
    response = client.post('/tasks/', task_data)
    assert response.status_code == 201
    pk = response.json()['id']
    url = f'/tasks/{pk}/'
    data = {**task_data, 'title': 'Study trees', 'action': 'edit'}
    assert client.post(url, data).json()['title'] == 'Study trees'
    assert client.post(url, {'action': 'complete'}).json()['completed'] is True
    assert client.post(url, {'action': 'reopen'}).json()['completed'] is False
    assert client.post(url, {'action': 'delete'}).status_code == 200
    assert not Task.objects.exists()


@pytest.mark.parametrize('invalid_case', ['missing_deadline', 'invalid_kind', 'empty_title'])
def test_invalid_task_is_not_saved(client, task_data, invalid_case):
    if invalid_case == 'missing_deadline':
        data = {'title': 'Missing deadline'}
    elif invalid_case == 'invalid_kind':
        data = {**task_data, 'kind': 'invalid'}
    else:
        data = {**task_data, 'title': ''}
    assert client.post('/tasks/', data).status_code == 400
    assert not Task.objects.exists()


def test_reminder_window_completion_and_snooze(client, fixed_now, reminder_ids):
    due = Task.objects.create(title='Soon', due_at=fixed_now + timedelta(hours=1))
    late = Task.objects.create(title='Late', due_at=fixed_now - timedelta(hours=2))
    Task.objects.create(title='Later', due_at=fixed_now + timedelta(days=3))
    Task.objects.create(title='Done', due_at=fixed_now, completed=True)
    assert set(reminder_ids()) == {due.id, late.id}
    assert client.post(f'/tasks/{due.id}/', {'action': 'snooze'}).status_code == 200
    assert due.id not in reminder_ids()
    due.refresh_from_db()
    assert due.snoozed_until == fixed_now + timedelta(minutes=15)
    due.snoozed_until = fixed_now - timedelta(seconds=1)
    due.save()
    assert due.id in reminder_ids()


def test_timezone_offset_is_preserved_as_instant(client, task_data):
    task_data['due_at'] = '2026-09-20T15:00:00+05:00'
    assert client.post('/tasks/', task_data).status_code == 201
    assert Task.objects.get().due_at == datetime(2026, 9, 20, 10, tzinfo=datetime_timezone.utc)


def test_mutations_require_post_and_csrf(client, task_data):
    task = Task.objects.create(title='Test', due_at=timezone.now())
    assert client.get(f'/tasks/{task.id}/').status_code == 405
    csrf_client = Client(enforce_csrf_checks=True)
    assert csrf_client.post('/tasks/', task_data).status_code == 403
    csrf_client.get('/')
    token = csrf_client.cookies['csrftoken'].value
    assert csrf_client.post('/tasks/', task_data, HTTP_X_CSRFTOKEN=token).status_code == 201


def test_home_and_not_found(client):
    response = client.get('/')
    assert response.status_code == 200
    assert 'Robot Care Buddy' in response.content.decode()
    assert client.post('/tasks/999/', {'action': 'delete'}).status_code == 404


def test_empty_database_returns_no_reminders(reminder_ids):
    assert reminder_ids() == []


def test_overdue_now_and_exactly_48_hours_are_included(fixed_now, reminder_ids):
    tasks = [
        Task.objects.create(title=title, due_at=fixed_now + offset)
        for title, offset in [
            ('Overdue', timedelta(days=-1)),
            ('Due now', timedelta()),
            ('Boundary', timedelta(hours=48)),
        ]
    ]
    assert reminder_ids() == [task.id for task in tasks]


def test_one_second_beyond_48_hours_is_excluded(fixed_now, reminder_ids):
    Task.objects.create(title='Outside window', due_at=fixed_now + timedelta(hours=48, seconds=1))
    assert reminder_ids() == []


def test_completed_tasks_are_excluded_even_when_overdue(fixed_now, reminder_ids):
    Task.objects.create(title='Already done', completed=True, due_at=fixed_now - timedelta(days=1))
    assert reminder_ids() == []


def test_unsnoozed_expired_and_exact_expiry_are_included(fixed_now, reminder_ids):
    tasks = [
        Task.objects.create(title=title, due_at=fixed_now, snoozed_until=snoozed_until)
        for title, snoozed_until in [
            ('No snooze', None),
            ('Expired', fixed_now - timedelta(seconds=1)),
            ('Expires now', fixed_now),
        ]
    ]
    assert reminder_ids() == [task.id for task in tasks]


def test_active_snooze_excludes_even_overdue_tasks(fixed_now, reminder_ids):
    Task.objects.create(
        title='Still snoozed',
        due_at=fixed_now - timedelta(days=1),
        snoozed_until=fixed_now + timedelta(seconds=1),
    )
    assert reminder_ids() == []


def test_reminders_post_is_rejected(client):
    assert client.post('/reminders/').status_code == 405


@pytest.mark.parametrize('endpoint,items,key', [
    ('/fun-fact/', FACTS, 'fact'),
    ('/joke/', JOKES, 'joke'),
])
def test_curated_content_does_not_repeat_previous(client, endpoint, items, key):
    first_response = client.get(endpoint)
    assert first_response.status_code == 200
    first = first_response.json()
    assert first[key] == items[first['id']]
    second_response = client.get(endpoint, {'previous': first['id']})
    assert second_response.status_code == 200
    second = second_response.json()
    assert second['id'] != first['id']
    assert second[key] == items[second['id']]
    assert client.post(endpoint).status_code == 405


@pytest.mark.parametrize('hours', [1, 24, 48])
def test_exact_boundaries_for_all_reminder_choices(fixed_now, reminder_ids, hours):
    boundary = Task.objects.create(title='Boundary', due_at=fixed_now + timedelta(hours=hours), reminder_hours=hours)
    Task.objects.create(title='Too early', due_at=fixed_now + timedelta(hours=hours, microseconds=1), reminder_hours=hours)
    overdue = Task.objects.create(title='Overdue', due_at=fixed_now - timedelta(days=1), reminder_hours=hours)
    Task.objects.create(title='Done', due_at=fixed_now, completed=True, reminder_hours=hours)
    Task.objects.create(title='Snoozed', due_at=fixed_now, snoozed_until=fixed_now + timedelta(minutes=1), reminder_hours=hours)
    assert set(reminder_ids()) == {boundary.id, overdue.id}


@pytest.mark.parametrize('hours', [1, 24, 48])
def test_reminder_choice_persists_when_edit_omits_it(client, task_data, hours):
    response = client.post('/tasks/', {**task_data, 'reminder_hours': hours})
    assert response.status_code == 201
    task = Task.objects.get(pk=response.json()['id'])
    assert task.reminder_hours == hours
    response = client.post(f'/tasks/{task.id}/', {**task_data, 'action': 'edit'})
    assert response.status_code == 200
    assert response.json()['reminder_hours'] == hours
    task.refresh_from_db()
    assert task.reminder_hours == hours


@pytest.mark.parametrize('value', ['', '2', '-1', 'abc'])
def test_invalid_reminder_choice_is_rejected(client, task_data, value):
    assert client.post('/tasks/', {**task_data, 'reminder_hours': value}).status_code == 400
    assert not Task.objects.exists()


def test_legacy_reminder_default_and_explicit_edit(client, task_data):
    response = client.post('/tasks/', task_data)
    assert response.status_code == 201
    assert response.json()['reminder_hours'] == 48
    response = client.post(f"/tasks/{response.json()['id']}/", {**task_data, 'action': 'edit', 'reminder_hours': 24})
    assert response.status_code == 200
    assert response.json()['reminder_hours'] == 24


@pytest.mark.parametrize('days', [1, 7])
def test_recurring_completion_preserves_history_and_settings(client, days):
    from zoneinfo import ZoneInfo
    task = Task.objects.create(title='Study', course='CSCI', kind='exam',
        due_at=datetime(2026, 12, 31, 12, tzinfo=ZoneInfo('America/Chicago')),
        repeat_days=days, repeat_timezone='America/Chicago', reminder_hours=1)
    response = client.post(f'/tasks/{task.id}/', {'action': 'complete'})
    assert response.status_code == 200
    assert response.json()['completed'] is True
    task.refresh_from_db()
    successor = Task.objects.get(completed=False)
    assert successor.due_at == task.due_at + timedelta(days=days)
    for field in ('title', 'course', 'kind', 'reminder_hours', 'repeat_days', 'repeat_timezone'):
        assert getattr(successor, field) == getattr(task, field)
    assert successor.snoozed_until is None
    for action in ('complete', 'reopen', 'complete', 'complete'):
        assert client.post(f'/tasks/{task.id}/', {'action': action}).status_code == 200
    assert Task.objects.count() == 2


@pytest.mark.parametrize('start,days,elapsed', [
    ('2026-03-07T09:00:00-06:00', 1, 23),
    ('2026-10-31T09:00:00-05:00', 1, 25),
    ('2026-03-01T09:00:00-06:00', 7, 167),
])
def test_recurring_task_preserves_local_hour_across_dst(client, task_data, start, days, elapsed):
    from zoneinfo import ZoneInfo
    response = client.post('/tasks/', {**task_data, 'due_at': start, 'repeat_days': days, 'repeat_timezone': 'America/Chicago'})
    assert response.status_code == 201
    task_id = response.json()['id']
    assert client.post(f'/tasks/{task_id}/', {'action': 'complete'}).status_code == 200
    original = Task.objects.get(pk=task_id)
    successor = Task.objects.get(completed=False)
    assert successor.due_at.astimezone(ZoneInfo('America/Chicago')).hour == 9
    assert successor.due_at - original.due_at == timedelta(hours=elapsed)


@pytest.mark.parametrize('changes', [{'repeat_days': 2}, {'repeat_timezone': 'Invalid/Zone'}])
def test_invalid_recurrence_is_rejected(client, task_data, changes):
    assert client.post('/tasks/', {**task_data, **changes}).status_code == 400
    assert not Task.objects.exists()


def test_recurrence_failure_rolls_back_completion(client, monkeypatch):
    task = Task.objects.create(title='Study', due_at=timezone.now(), repeat_days=1)
    def fail(*args, **kwargs):
        raise RuntimeError('Failed')
    monkeypatch.setattr('planner.views.Task.objects.create', fail)
    with pytest.raises(RuntimeError, match='Failed'):
        client.post(f'/tasks/{task.id}/', {'action': 'complete'})
    task.refresh_from_db()
    assert task.completed is False
    assert task.recurrence_generated is False
    assert Task.objects.count() == 1


def test_nonrecurring_completion_and_stop_repeating(client, task_data):
    task = Task.objects.create(title='Study', due_at=timezone.now())
    assert client.post(f'/tasks/{task.id}/', {'action': 'complete'}).status_code == 200
    assert Task.objects.count() == 1
    assert client.post(f'/tasks/{task.id}/', {**task_data, 'action': 'edit', 'repeat_days': 7}).status_code == 200
    assert client.post(f'/tasks/{task.id}/', {'action': 'reopen'}).status_code == 200
    assert client.post(f'/tasks/{task.id}/', {'action': 'complete'}).status_code == 200
    successor = Task.objects.get(completed=False)
    assert client.post(f'/tasks/{successor.id}/', {**task_data, 'action': 'edit', 'repeat_days': 0}).status_code == 200
    assert client.post(f'/tasks/{successor.id}/', {'action': 'complete'}).status_code == 200
    assert Task.objects.count() == 2


@pytest.fixture
def quiet_data():
    return {'enabled': 'on', 'start': '22:00', 'end': '08:00', 'timezone': 'America/Chicago'}


def test_quiet_hours_save_reload_and_disable(client, quiet_data):
    assert client.get('/quiet-hours/').json()['enabled'] is False
    assert client.post('/quiet-hours/', quiet_data).status_code == 200
    saved = client.get('/quiet-hours/').json()
    assert (saved['start'], saved['end'], saved['timezone']) == ('22:00', '08:00', 'America/Chicago')
    assert saved['enabled'] is True
    response = client.post('/quiet-hours/', {**quiet_data, 'enabled': ''})
    assert response.status_code == 200
    assert response.json()['enabled'] is False


@pytest.mark.parametrize('changes', [{'start': '25:00'}, {'end': ''}, {'timezone': 'Invalid/Zone'}, {'start': '08:00'}])
def test_invalid_quiet_hours_preserve_saved_settings(client, quiet_data, changes):
    assert client.post('/quiet-hours/', quiet_data).status_code == 200
    saved = client.get('/quiet-hours/').json()
    assert client.post('/quiet-hours/', {**quiet_data, **changes}).status_code == 400
    assert client.get('/quiet-hours/').json() == saved


@pytest.mark.parametrize('instant,active', [
    ('2026-09-29T21:59:59-05:00', False),
    ('2026-09-29T22:00:00-05:00', True),
    ('2026-09-30T00:00:00-05:00', True),
    ('2026-09-30T07:59:59-05:00', True),
    ('2026-09-30T08:00:00-05:00', False),
])
def test_quiet_hours_boundaries_and_reminder_resume(client, quiet_data, monkeypatch, instant, active):
    now = datetime.fromisoformat(instant)
    monkeypatch.setattr('planner.views.timezone.now', lambda: now)
    assert client.post('/quiet-hours/', quiet_data).status_code == 200
    task = Task.objects.create(title='Overdue', due_at=now - timedelta(days=1))
    Task.objects.create(title='Done', due_at=task.due_at, completed=True)
    Task.objects.create(title='Snoozed', due_at=task.due_at, snoozed_until=now + timedelta(days=1))
    response = client.get('/reminders/')
    assert response.status_code == 200
    result = response.json()
    assert result['quiet'] is active
    assert result['now'] == now.isoformat()
    assert [item['id'] for item in result['tasks']] == ([] if active else [task.id])


@pytest.mark.parametrize('instant,active', [
    ('2026-03-07T14:59:59+00:00', False),
    ('2026-03-07T15:00:00+00:00', True),
    ('2026-03-08T14:00:00+00:00', True),
    ('2026-03-08T22:00:00+00:00', False),
])
def test_same_day_quiet_hours_timezone_and_dst(client, quiet_data, instant, active):
    from .models import QuietHours
    assert client.post('/quiet-hours/', {**quiet_data, 'start': '09:00', 'end': '17:00'}).status_code == 200
    settings = QuietHours.objects.get(pk=1)
    now = datetime.fromisoformat(instant)
    assert settings.is_active(now) is active
    settings.enabled = False
    assert settings.is_active(now) is False


def test_disabled_quiet_hours_allow_reminders(client, quiet_data, fixed_now, reminder_ids):
    assert client.post('/quiet-hours/', {**quiet_data, 'enabled': ''}).status_code == 200
    task = Task.objects.create(title='Due now', due_at=fixed_now)
    assert reminder_ids() == [task.id]
    assert client.get('/reminders/').json()['quiet'] is False


def test_quiet_hours_csrf_and_methods(client):
    csrf_client = Client(enforce_csrf_checks=True)
    assert csrf_client.post('/quiet-hours/', {}).status_code == 403
    assert client.delete('/quiet-hours/').status_code == 405
