from django.db import models

class Task(models.Model):
    title = models.CharField(max_length=120)
    course = models.CharField(max_length=80, blank=True)
    kind = models.CharField(max_length=10, choices=[('assignment','Assignment'),('exam','Exam')], default='assignment')
    due_at = models.DateTimeField()
    reminder_hours = models.PositiveSmallIntegerField(choices=[(1, '1 hour'), (24, '1 day'), (48, '2 days')], default=48)
    repeat_days = models.PositiveSmallIntegerField(choices=[(0, 'Never'), (1, 'Daily'), (7, 'Weekly')], default=0)
    repeat_timezone = models.CharField(max_length=64, default='UTC')
    recurrence_generated = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)
    snoozed_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['completed', 'due_at', 'id']


class QuietHours(models.Model):
    """One persisted preference set for this single-user planner."""
    enabled = models.BooleanField(default=False)
    start = models.TimeField(default='22:00')
    end = models.TimeField(default='08:00')
    timezone = models.CharField(max_length=64, default='UTC')

    def is_active(self, now):
        from zoneinfo import ZoneInfo
        if not self.enabled:
            return False
        current = now.astimezone(ZoneInfo(self.timezone)).time()
        if self.start < self.end:
            return self.start <= current < self.end
        return current >= self.start or current < self.end
