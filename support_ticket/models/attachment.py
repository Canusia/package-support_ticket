import uuid
from django.core.exceptions import ValidationError
from django.db import models

from cis.storage_backend import PrivateMediaStorage


class TicketAttachment(models.Model):
    """A file attached to either a Ticket or a TicketNote (exactly one)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ticket = models.ForeignKey(
        'Ticket', on_delete=models.CASCADE, null=True, blank=True,
        related_name='attachments')
    note = models.ForeignKey(
        'TicketNote', on_delete=models.CASCADE, null=True, blank=True,
        related_name='attachments')

    media = models.FileField(
        storage=PrivateMediaStorage(), upload_to='support_ticket/attachments/%Y/%m/',
        max_length=500)
    uploaded_by = models.ForeignKey(
        'cis.CustomUser', on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support_ticket'
        ordering = ['uploaded_on']

    def clean(self):
        if bool(self.ticket_id) == bool(self.note_id):
            raise ValidationError(
                'A TicketAttachment must reference exactly one of ticket or note.')

    @property
    def filename(self):
        return self.media.name.rsplit('/', 1)[-1] if self.media else ''
