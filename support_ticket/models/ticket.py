# users/models.py
import uuid

from django.contrib.auth import get_user_model
from django.db import models

from cis.models.note import Note

class TicketType(models.Model):
    """Ticket Type model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, blank=True)

    STUDENTS = 'Students'
    SCHOOL_ADMINS = 'High School Administrators'
    INSTRUCTORS = 'Instructors'
    APPLIES_TO = [
        (STUDENTS, STUDENTS),
        (SCHOOL_ADMINS, SCHOOL_ADMINS),
        (INSTRUCTORS, INSTRUCTORS),
    ]
    applies_to = models.CharField(max_length=30, choices=APPLIES_TO)

    assigned_to = models.ForeignKey(
        'cis.CustomUser', on_delete=models.PROTECT, blank=True, null=True)

    notify_users = models.ManyToManyField(
        'cis.CustomUser', blank=True, related_name='notify_ticket_types')
    notify_emails = models.TextField(
        blank=True, help_text='Comma-separated extra email addresses to notify on submission.')
    requires_attachment = models.BooleanField(
        default=False, help_text='Require at least one file when a ticket of this type is created.')
    email_assignee = models.BooleanField(
        default=False, verbose_name='Email assignee',
        help_text='Email the assigned person whenever a ticket of this type is assigned to them.')

    class Meta:
        unique_together = ['name', 'applies_to']

    def __str__(self):
        return self.name

    def notify_recipient_emails(self):
        """All addresses to email when a ticket of this type is submitted."""
        emails = list(
            self.notify_users.values_list('email', flat=True))
        for raw in (self.notify_emails or '').split(','):
            addr = raw.strip()
            if addr:
                emails.append(addr)
        # de-dupe, preserve order
        seen, out = set(), []
        for e in emails:
            if e and e not in seen:
                seen.add(e)
                out.append(e)
        return out

class Ticket(models.Model):
    """
    Ticket Model
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_type = models.ForeignKey('TicketType', on_delete=models.PROTECT)

    submitted_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.PROTECT
    )
    assigned_to = models.ForeignKey(
        get_user_model(),
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='assigned_to_ticket_set'
    )
    message = models.TextField(blank=True)

    status = models.CharField(max_length=40, default='Submitted')
    # Defaults to the active term when the ticket is created (signals.py); CE
    # can change it on the detail page. Null for tickets that predate it.
    term = models.ForeignKey(
        'cis.Term', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='support_tickets')
    submitted_on = models.DateTimeField(auto_now_add=True)
    last_updated_on = models.DateTimeField(auto_now=True)


class TicketNote(Note, models.Model):
    """
    Notes/Updates for Support Ticket
    """
    support_ticket = models.ForeignKey(
        'Ticket',
        on_delete=models.PROTECT,
        blank=True,
        null=True)

    note_type = models.CharField(
        max_length=10,
        choices=(
            ('Public', 'Public'),
            ('Internal', 'Internal'),
        )
    )

    # Who this note was actually emailed to (comma-separated, after Debug-mode
    # redirection) and when it was queued; empty/None when it was not emailed.
    emailed_to = models.TextField(blank=True, default='')
    emailed_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['createdon']

    @classmethod
    def add_note(cls, request, note_form):
        note = cls()
        note.support_ticket = Ticket.objects.get(
            pk=note_form.cleaned_data['add_to'])

        note.createdby = request.user
        note.note = note_form.cleaned_data['note']

        note.save()
        return note
