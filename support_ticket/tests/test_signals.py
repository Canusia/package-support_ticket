from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from mailer.engine import send_all

from cis.models.settings import Setting
from ..models.ticket import Ticket, TicketType, TicketNote
from ..settings.support_ticket_settings import support_ticket_settings as STS

User = get_user_model()

# locmem backend for both Django mail and django-mailer's delivery engine.
LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def _flush():
    """Signals queue mail via django-mailer; flush the queue into mail.outbox."""
    send_all()


def _configure(**overrides):
    value = {
        'is_active': 'Yes', 'from_email': 'support@example.com',
        'statuses': 'Submitted\nPending\nClosed',
        'submission_subject': 'Received', 'submission_email': 'Got {{ticket_type}}',
        'note_subject': 'Note', 'note_email': '{{update}}',
        'status_closed_notify': True, 'status_closed_subject': 'Closed',
        'status_closed_email': 'Your ticket is {{status}}',
    }
    value.update(overrides)
    Setting.objects.update_or_create(key=STS.key, defaults={'value': value})


@override_settings(EMAIL_BACKEND=LOCMEM, MAILER_EMAIL_BACKEND=LOCMEM)
class SignalTests(TestCase):
    def setUp(self):
        _configure()
        self.submitter = User.objects.create(
            username='stu', email='stu@example.com', first_name='Sam')
        self.ce = User.objects.create(
            username='ce', email='ce@example.com', first_name='Cee')
        self.tt = TicketType.objects.create(
            name='Tech', applies_to='Students', assigned_to=self.ce,
            notify_emails='watch@example.com')

    def test_create_sets_default_assignee_and_status_and_emails_notify_list(self):
        mail.outbox = []
        t = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.submitter, message='help', status='')
        t.refresh_from_db()
        self.assertEqual(t.assigned_to, self.ce)         # default assignee copied
        self.assertEqual(t.status, 'Submitted')          # default status applied
        # submission email went to the type's notify list (assignee + extra email)
        _flush()
        recipients = {addr for m in mail.outbox for addr in m.to}
        self.assertIn('watch@example.com', recipients)

    def test_status_change_emails_submitter_with_template(self):
        t = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.submitter, message='help')
        mail.outbox = []
        t.status = 'Closed'
        t.save()
        _flush()
        self.assertTrue(any('stu@example.com' in m.to for m in mail.outbox))
        self.assertTrue(any('Closed' in m.subject for m in mail.outbox))

    def test_inactive_mode_sends_nothing(self):
        _configure(is_active='No')
        mail.outbox = []
        Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.submitter, message='x')
        _flush()
        self.assertEqual(len(mail.outbox), 0)

    def test_third_party_note_on_unassigned_ticket_notifies_default_to(self):
        """Bug #8: third-party note on unassigned ticket must fall back to default_to."""
        _configure(default_to='ops@example.com')
        # TicketType with NO default assignee
        tt_unassigned = TicketType.objects.create(
            name='Unassigned', applies_to='Students')
        ticket = Ticket.objects.create(
            ticket_type=tt_unassigned, submitted_by=self.submitter,
            message='help', assigned_to=None)
        # Ensure no assignee was set by the signal
        ticket.refresh_from_db()
        self.assertIsNone(ticket.assigned_to_id)

        third_party = User.objects.create(
            username='third', email='third@example.com')
        mail.outbox = []
        TicketNote.objects.create(
            support_ticket=ticket,
            note='third party note',
            createdby=third_party,
            note_type='Public',
        )
        _flush()
        recipients = {addr for m in mail.outbox for addr in m.to}
        self.assertIn('ops@example.com', recipients)
