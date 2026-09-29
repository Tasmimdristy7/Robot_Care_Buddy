from datetime import timedelta
from django.test import TestCase, Client
from django.utils import timezone
from .models import Task

class BuddyTests(TestCase):
    def data(self, **extra):
        return dict(title='Study graphs',course='CSCI 713',kind='exam',due_at=(timezone.now()+timedelta(hours=20)).isoformat(),**extra)

    def test_create_edit_complete_reopen_delete(self):
        r=self.client.post('/tasks/',self.data());self.assertEqual(r.status_code,201)
        pk=r.json()['id'];url=f'/tasks/{pk}/'
        data=self.data();data.update(title='Study trees',action='edit')
        self.assertEqual(self.client.post(url,data).json()['title'],'Study trees')
        self.assertTrue(self.client.post(url,{'action':'complete'}).json()['completed'])
        self.assertFalse(self.client.post(url,{'action':'reopen'}).json()['completed'])
        self.assertEqual(self.client.post(url,{'action':'delete'}).status_code,200)
        self.assertFalse(Task.objects.exists())

    def test_invalid_task_is_not_saved(self):
        for data in [{'title':'Missing deadline'},dict(self.data(),kind='invalid'),dict(self.data(),title='')]:
            self.assertEqual(self.client.post('/tasks/',data).status_code,400)
        self.assertFalse(Task.objects.exists())

    def test_reminder_window_completion_and_snooze(self):
        now=timezone.now()
        due=Task.objects.create(title='Soon',due_at=now+timedelta(hours=1))
        late=Task.objects.create(title='Late',due_at=now-timedelta(hours=2))
        Task.objects.create(title='Later',due_at=now+timedelta(days=3))
        Task.objects.create(title='Done',due_at=now,completed=True)
        self.assertEqual({t['id'] for t in self.client.get('/reminders/').json()['tasks']},{due.id,late.id})
        self.client.post(f'/tasks/{due.id}/',{'action':'snooze'})
        self.assertNotIn(due.id,[t['id'] for t in self.client.get('/reminders/').json()['tasks']])
        due.refresh_from_db();self.assertGreater(due.snoozed_until,now)
        due.snoozed_until=now-timedelta(seconds=1);due.save()
        self.assertIn(due.id,[t['id'] for t in self.client.get('/reminders/').json()['tasks']])

    def test_timezone_offset_is_preserved_as_instant(self):
        data=self.data();data['due_at']='2026-09-20T15:00:00+05:00'
        self.client.post('/tasks/',data)
        self.assertEqual(Task.objects.get().due_at.hour,10)

    def test_mutations_require_post_and_csrf(self):
        task=Task.objects.create(title='Test',due_at=timezone.now())
        self.assertEqual(self.client.get(f'/tasks/{task.id}/').status_code,405)
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/tasks/',self.data()).status_code,403)
        client.get('/');token=client.cookies['csrftoken'].value
        self.assertEqual(client.post('/tasks/',self.data(),HTTP_X_CSRFTOKEN=token).status_code,201)

    def test_home_and_not_found(self):
        self.assertContains(self.client.get('/'),'Robot Care Buddy')
        self.assertEqual(self.client.post('/tasks/999/',{'action':'delete'}).status_code,404)


class FunFactTests(TestCase):
    def test_fact_is_from_curated_list_and_does_not_repeat_previous(self):
        from .facts import FACTS
        first = self.client.get('/fun-fact/').json()
        self.assertEqual(first['fact'], FACTS[first['id']])
        second = self.client.get('/fun-fact/', {'previous':first['id']}).json()
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(self.client.post('/fun-fact/').status_code, 405)


class JokeTests(TestCase):
    def test_random_joke_and_no_immediate_repeat(self):
        from .facts import JOKES
        first = self.client.get('/joke/').json()
        self.assertEqual(first['joke'], JOKES[first['id']])
        second = self.client.get('/joke/', {'previous':first['id']}).json()
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(self.client.post('/joke/').status_code, 405)


class ReminderLeadTimeTests(TestCase):
    def test_exact_boundaries_for_all_choices(self):
        from unittest.mock import patch
        now = timezone.now()
        for hours in (1, 24, 48):
            with self.subTest(hours=hours):
                Task.objects.all().delete()
                boundary = Task.objects.create(title='Boundary', due_at=now+timedelta(hours=hours), reminder_hours=hours)
                Task.objects.create(title='Too early', due_at=now+timedelta(hours=hours, microseconds=1), reminder_hours=hours)
                overdue = Task.objects.create(title='Overdue', due_at=now-timedelta(days=1), reminder_hours=hours)
                Task.objects.create(title='Done', due_at=now, completed=True, reminder_hours=hours)
                Task.objects.create(title='Snoozed', due_at=now, snoozed_until=now+timedelta(minutes=1), reminder_hours=hours)
                with patch('planner.views.timezone.now', return_value=now):
                    self.assertEqual({t['id'] for t in self.client.get('/reminders/').json()['tasks']}, {boundary.id, overdue.id})

    def test_persistence_edit_validation_and_legacy_default(self):
        data = dict(title='Study', kind='assignment', due_at=timezone.now().isoformat())
        for hours in (1, 24, 48):
            response = self.client.post('/tasks/', dict(data, reminder_hours=hours))
            self.assertEqual(response.status_code, 201)
            task = Task.objects.get(pk=response.json()['id'])
            self.assertEqual(task.reminder_hours, hours)
            response = self.client.post(f'/tasks/{task.id}/', dict(data, action='edit'))
            self.assertEqual(response.json()['reminder_hours'], hours)
        for value in ('', '2', '-1', 'abc'):
            self.assertEqual(self.client.post('/tasks/', dict(data, reminder_hours=value)).status_code, 400)
        self.assertEqual(self.client.post('/tasks/', data).json()['reminder_hours'], 48)
        task = Task.objects.first()
        self.assertEqual(self.client.post(f'/tasks/{task.id}/', dict(data, action='edit', reminder_hours=24)).json()['reminder_hours'], 24)


class RecurringTaskTests(TestCase):
    def test_daily_and_weekly_completion_preserves_history_and_settings(self):
        for days in (1, 7):
            with self.subTest(days=days):
                Task.objects.all().delete()
                task = Task.objects.create(title='Study', course='CSCI', kind='exam',
                    due_at=timezone.datetime(2026, 12, 31, 12, tzinfo=timezone.get_default_timezone()),
                    repeat_days=days, repeat_timezone='America/Chicago', reminder_hours=1)
                response = self.client.post(f'/tasks/{task.id}/', {'action':'complete'})
                self.assertTrue(response.json()['completed'])
                task.refresh_from_db()
                successor = Task.objects.get(completed=False)
                self.assertEqual(successor.due_at, task.due_at + timedelta(days=days))
                for field in ('title', 'course', 'kind', 'reminder_hours', 'repeat_days', 'repeat_timezone'):
                    self.assertEqual(getattr(successor, field), getattr(task, field))
                self.assertIsNone(successor.snoozed_until)
                for action in ('complete', 'reopen', 'complete', 'complete'):
                    self.assertEqual(self.client.post(f'/tasks/{task.id}/', {'action':action}).status_code, 200)
                self.assertEqual(Task.objects.count(), 2)

    def test_timezone_dst_and_validation(self):
        from zoneinfo import ZoneInfo
        for start, days, elapsed in [('2026-03-07T09:00:00-06:00', 1, 23), ('2026-10-31T09:00:00-05:00', 1, 25), ('2026-03-01T09:00:00-06:00', 7, 167)]:
            data = dict(title='Study', kind='assignment', due_at=start, repeat_days=days, repeat_timezone='America/Chicago')
            task_id = self.client.post('/tasks/', data).json()['id']
            self.client.post(f'/tasks/{task_id}/', {'action':'complete'})
            original = Task.objects.get(pk=task_id)
            successor = Task.objects.order_by('-id').first()
            self.assertEqual(successor.due_at.astimezone(ZoneInfo('America/Chicago')).hour, 9)
            self.assertEqual(successor.due_at - original.due_at, timedelta(hours=elapsed))
        self.assertEqual(self.client.post('/tasks/', dict(data, repeat_days=2)).status_code, 400)
        self.assertEqual(self.client.post('/tasks/', dict(data, repeat_timezone='Invalid/Zone')).status_code, 400)

    def test_failure_rolls_back_completion(self):
        from unittest.mock import patch
        task = Task.objects.create(title='Study', due_at=timezone.now(), repeat_days=1)
        with patch('planner.views.Task.objects.create', side_effect=RuntimeError('Failed')):
            with self.assertRaises(RuntimeError):
                self.client.post(f'/tasks/{task.id}/', {'action':'complete'})
        task.refresh_from_db()
        self.assertFalse(task.completed)
        self.assertFalse(task.recurrence_generated)

    def test_nonrecurring_completion_and_stop_repeating(self):
        task = Task.objects.create(title='Study', due_at=timezone.now())
        self.client.post(f'/tasks/{task.id}/', {'action':'complete'})
        self.assertEqual(Task.objects.count(), 1)
        self.client.post(f'/tasks/{task.id}/', dict(action='edit', title='Study', kind='assignment', due_at=task.due_at.isoformat(), repeat_days=7))
        self.client.post(f'/tasks/{task.id}/', {'action':'reopen'})
        self.client.post(f'/tasks/{task.id}/', {'action':'complete'})
        successor = Task.objects.get(completed=False)
        self.client.post(f'/tasks/{successor.id}/', dict(action='edit', title='Study', kind='assignment', due_at=successor.due_at.isoformat(), repeat_days=0))
        self.client.post(f'/tasks/{successor.id}/', {'action':'complete'})
        self.assertEqual(Task.objects.count(), 2)
