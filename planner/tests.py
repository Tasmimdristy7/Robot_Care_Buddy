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
