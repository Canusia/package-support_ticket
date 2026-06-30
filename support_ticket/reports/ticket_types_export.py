import io
import csv

from django import forms
from django.urls import reverse_lazy
from django.core.files.base import ContentFile

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from cis.backends.storage_backend import PrivateMediaStorage
from myce_tenant_configs.services.bulk_enroller import _csv_safe

from support_ticket.models.ticket import TicketType

HEADER = ['Name', 'Applies To', 'Default Assignee', 'Notify Users',
          'Notify Emails', 'Requires Attachment']


class ticket_types_export(forms.Form):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.helper = FormHelper()
        self.helper.attrs = {'target': '_blank'}
        self.helper.form_method = 'POST'
        if request is not None:
            self.helper.form_action = reverse_lazy(
                'report:run_report', args=[request.GET.get('report_id')])
        self.helper.add_input(Submit('submit', 'Generate Export'))

    def get_rows(self):
        rows = [list(HEADER)]
        qs = TicketType.objects.select_related('assigned_to').prefetch_related('notify_users')
        for tt in qs.order_by('applies_to', 'name'):
            assignee = tt.assigned_to.email if tt.assigned_to_id else ''
            notify_users = ', '.join(tt.notify_users.values_list('email', flat=True))
            rows.append([
                _csv_safe(tt.name),
                _csv_safe(tt.applies_to),
                _csv_safe(assignee),
                _csv_safe(notify_users),
                _csv_safe(tt.notify_emails or ''),
                'Yes' if tt.requires_attachment else 'No',
            ])
        return rows

    def run(self, task, data):
        stream = io.StringIO()
        writer = csv.writer(stream)
        for row in self.get_rows():
            writer.writerow(row)
        path = f"reports/{task.id}/ticket-types-export.csv"
        storage = PrivateMediaStorage()
        path = storage.save(path, ContentFile(stream.getvalue().encode('utf-8')))
        return storage.url(path)
