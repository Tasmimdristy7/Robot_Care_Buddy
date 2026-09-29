from django.db import models

class Task(models.Model):
    title = models.CharField(max_length=120)
    course = models.CharField(max_length=80, blank=True)
    kind = models.CharField(max_length=10, choices=[('assignment','Assignment'),('exam','Exam')], default='assignment')
    due_at = models.DateTimeField()
    reminder_hours = models.PositiveSmallIntegerField(choices=[(1, '1 hour'), (24, '1 day'), (48, '2 days')], default=48)
    completed = models.BooleanField(default=False)
    snoozed_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['completed', 'due_at', 'id']
