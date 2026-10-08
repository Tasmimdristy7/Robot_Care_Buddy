from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django import forms
from .models import Task

class TaskForm(forms.ModelForm):
    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            instance = kwargs.get('instance')
            for field, default in [('reminder_hours', 48), ('repeat_days', 0), ('repeat_timezone', 'UTC')]:
                if field not in data:
                    data[field] = getattr(instance, field) if instance else default
        super().__init__(data, *args, **kwargs)

    def clean_repeat_timezone(self):
        value = self.cleaned_data['repeat_timezone']
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise forms.ValidationError('Choose a valid timezone.')
        return value

    class Meta:
        model = Task
        fields = ['title', 'course', 'kind', 'due_at', 'reminder_hours', 'repeat_days', 'repeat_timezone']
        widgets = {'due_at': forms.DateTimeInput(attrs={'type':'datetime-local'})}


class QuietHoursForm(forms.ModelForm):
    def clean_timezone(self):
        value = self.cleaned_data['timezone']
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise forms.ValidationError('Choose a valid timezone.')
        return value

    def clean(self):
        data = super().clean()
        if data.get('enabled') and data.get('start') == data.get('end'):
            raise forms.ValidationError('Start and end must differ. Uncheck Enable to turn quiet hours off.')
        return data

    class Meta:
        from .models import QuietHours
        model = QuietHours
        fields = ['enabled', 'start', 'end', 'timezone']
