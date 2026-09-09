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
