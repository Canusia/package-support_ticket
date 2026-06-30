"""
Bulk action forms for CE support-ticket operations.

Design note: both forms use QuerySet.update() which bypasses the per-ticket
post_save signal (ticket_post_save / ticket_pre_save).  This is intentional —
mirroring the students change_application_status pattern — to avoid email
storms when bulk-updating many tickets.  Single-ticket status changes via the
detail page still trigger the signal and send per-status notification emails.
If per-ticket emails on bulk are ever required, replace update() with a loop
calling record.save() for each ticket.
"""
import uuid
from collections import OrderedDict

from django import forms

from cis.models.customuser import CustomUser
from support_ticket.settings.support_ticket_settings import (
    support_ticket_settings as STS,
)


def _valid_uuids(ids):
    """Return only the items from *ids* that are valid UUID strings."""
    out = []
    for i in ids or []:
        try:
            uuid.UUID(str(i))
            out.append(i)
        except (ValueError, TypeError, AttributeError):
            pass
    return out


class BulkTicketStatusForm(forms.Form):
    status = forms.ChoiceField(
        label='New Status',
        choices=[],
        required=True,
    )

    def __init__(self, ticket_ids=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ticket_ids = _valid_uuids(ticket_ids)
        statuses = STS.get_statuses()
        self.fields['status'].choices = [(s, s) for s in statuses]

    def save(self, request):
        from support_ticket.models.ticket import Ticket
        count = Ticket.objects.filter(id__in=self._ticket_ids).update(
            status=self.cleaned_data['status']
        )
        return count


class BulkTicketAssignForm(forms.Form):
    assigned_to = forms.ModelChoiceField(
        label='Assign To',
        queryset=CustomUser.objects.filter(
            groups__name='ce', is_active=True,
        ).order_by('last_name', 'first_name'),
        required=True,
    )

    def __init__(self, ticket_ids=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ticket_ids = _valid_uuids(ticket_ids)

    def save(self, request):
        from support_ticket.models.ticket import Ticket
        count = Ticket.objects.filter(id__in=self._ticket_ids).update(
            assigned_to=self.cleaned_data['assigned_to']
        )
        return count
