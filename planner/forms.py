from django import forms
from .models import Task

class TaskForm(forms.ModelForm):
    def __init__(self, data=None, *args, **kwargs):
        if data is not None and 'reminder_hours' not in data:
            data = data.copy()
            instance = kwargs.get('instance')
            data['reminder_hours'] = instance.reminder_hours if instance else 48
        super().__init__(data, *args, **kwargs)

    class Meta:
        model = Task
        fields = ['title', 'course', 'kind', 'due_at', 'reminder_hours']
        widgets = {'due_at': forms.DateTimeInput(attrs={'type':'datetime-local'})}
