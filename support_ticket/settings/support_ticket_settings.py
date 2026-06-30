from django import forms
from django.http import JsonResponse
from django.template import Context, Template
from django.urls import reverse_lazy
from django.utils.text import slugify

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from cis.models.settings import Setting
from cis.validators import validate_html_short_code
from support_ticket.constants import DEFAULT_STATUSES

WHO_CHOICES = [
    ('student', 'Students'),
    ('instructor', 'Instructors'),
    ('highschool_admin', 'High School Administrators'),
]


class SettingForm(forms.Form):
    is_active = forms.ChoiceField(
        choices=[('Yes', 'Active'), ('No', 'Off'), ('Debug', 'Debug')])
    who_can_start = forms.MultipleChoiceField(
        choices=WHO_CHOICES, required=False,
        help_text='Roles allowed to open new tickets.')
    from_email = forms.EmailField(
        required=False, help_text='Sender address for ticket emails.')
    default_to = forms.CharField(
        widget=forms.Textarea, required=False,
        help_text='Fallback recipients (comma-separated) when no assignee/notify list.')
    statuses = forms.CharField(
        widget=forms.Textarea,
        help_text='One status per line. The FIRST line is the default status for new tickets.')
    submission_subject = forms.CharField(required=False)
    submission_email = forms.CharField(
        widget=forms.Textarea, required=False, validators=[validate_html_short_code],
        help_text='Sent to the ticket type notify list on submission. '
                  'Shortcodes: {{first_name}}, {{ticket_type}}, {{message}}, {{site_url}}.')
    note_subject = forms.CharField(required=False)
    note_email = forms.CharField(
        widget=forms.Textarea, required=False, validators=[validate_html_short_code],
        help_text='Sent when a note is added. Shortcodes: {{update}}, {{site_url}}.')

    def _static_to_python(self):
        cd = self.cleaned_data
        return {
            'is_active': cd['is_active'],
            'who_can_start': cd['who_can_start'],
            'from_email': cd['from_email'],
            'default_to': cd['default_to'],
            'statuses': cd['statuses'],
            'submission_subject': cd['submission_subject'],
            'submission_email': cd['submission_email'],
            'note_subject': cd['note_subject'],
            'note_email': cd['note_email'],
        }


class support_ticket_settings(SettingForm):
    # 48 chars — fits Setting.key max_length=50.
    # Uses the outer/shim path so import_string works in both dev and prod
    # (inner path 'support_ticket.support_ticket.settings.support_ticket_settings'
    # is 63 chars and exceeds the DB constraint; a later migration can lengthen it).
    key = 'support_ticket.settings.support_ticket_settings'

    # ---- helper API (used by signals/forms; classmethods so no instance needed) ----
    @classmethod
    def from_db(cls):
        try:
            return Setting.objects.get(key=cls.key).value or {}
        except Setting.DoesNotExist:
            return {}

    @classmethod
    def get_statuses(cls):
        raw = (cls.from_db().get('statuses') or '').strip()
        if not raw:
            return list(DEFAULT_STATUSES)
        return [line.strip() for line in raw.splitlines() if line.strip()]

    @classmethod
    def get_default_status(cls):
        return cls.get_statuses()[0]

    @classmethod
    def is_active(cls):
        return cls.from_db().get('is_active', 'Yes')

    @classmethod
    def can_start(cls, role):
        cfg = cls.from_db()
        allowed = cfg.get('who_can_start')
        if allowed is None:
            return True  # unconfigured → permissive default (matches pre-feature behavior)
        return role in allowed

    @classmethod
    def status_template(cls, status):
        cfg = cls.from_db()
        slug = slugify(status)
        if f'status_{slug}_email' not in cfg and f'status_{slug}_subject' not in cfg:
            return None
        return {
            'notify': bool(cfg.get(f'status_{slug}_notify')),
            'subject': cfg.get(f'status_{slug}_subject', ''),
            'email': cfg.get(f'status_{slug}_email', ''),
        }

    # ---- setting-framework lifecycle ----
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

        # dynamically add per-status template fields from the saved status list
        for status in self.get_statuses():
            slug = slugify(status)
            self.fields[f'status_{slug}_notify'] = forms.BooleanField(
                required=False, label=f"'{status}' — email submitter on entering this status")
            self.fields[f'status_{slug}_subject'] = forms.CharField(
                required=False, label=f"'{status}' subject")
            self.fields[f'status_{slug}_email'] = forms.CharField(
                widget=forms.Textarea, required=False, validators=[validate_html_short_code],
                label=f"'{status}' email body",
                help_text='Shortcodes: {{first_name}}, {{status}}, {{ticket_type}}, {{site_url}}.')

        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        if request is not None:
            self.helper.form_action = reverse_lazy(
                'setting:run_record', args=[request.GET.get('report_id')])
        self.helper.add_input(Submit('submit', 'Save Settings'))

        # populate initial values
        for name, value in self.from_db().items():
            if name in self.fields:
                self.fields[name].initial = value

    def _to_python(self):
        data = self._static_to_python()
        for status in self.get_statuses():
            slug = slugify(status)
            for suffix in ('notify', 'subject', 'email'):
                fname = f'status_{slug}_{suffix}'
                if fname in self.cleaned_data:
                    data[fname] = self.cleaned_data[fname]
        return data

    def install(self):
        defaults = {
            'is_active': 'Yes',
            'who_can_start': ['student', 'instructor', 'highschool_admin'],
            'from_email': '',
            'default_to': '',
            'statuses': '\n'.join(DEFAULT_STATUSES),
            'submission_subject': 'We received your support request',
            'submission_email': 'A new {{ticket_type}} request was submitted.\n\n{{message}}',
            'note_subject': 'Update added to your support request',
            'note_email': 'An update was posted:\n\n{{update}}\n\nLog in at {{site_url}}.',
        }
        Setting.objects.update_or_create(key=self.key, defaults={'value': defaults})

    def run_record(self):
        setting, _ = Setting.objects.get_or_create(key=self.key)
        setting.value = self._to_python()
        setting.save()
        return JsonResponse({'message': 'Successfully saved settings', 'status': 'success'})

    def preview(self, request, field_name):
        from django.shortcuts import render
        cfg = self.from_db()
        body = Template(cfg.get(field_name, ''))
        ctx = Context({
            'first_name': request.user.first_name, 'status': 'Sample Status',
            'ticket_type': 'Sample Type', 'message': 'Sample message',
            'update': 'Sample update', 'site_url': 'https://example.com',
        })
        return render(request, 'cis/email.html', {'message': body.render(ctx)})
