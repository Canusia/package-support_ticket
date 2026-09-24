"""Email the assignee when a ticket is assigned, if its type has `email_assignee` checked."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase, override_settings

from mailer.engine import send_all

from cis.models.settings import Setting
from ..forms.bulk import BulkTicketAssignForm
from ..forms.types import TicketTypeForm
from ..models.ticket import Ticket, TicketType
from ..settings.support_ticket_settings import support_ticket_settings as STS

User = get_user_model()
LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def _configure(**overrides):
    value = {
        'is_active': 'Yes', 'from_email': 'support@example.com',
        'statuses': 'Submitted\nPending\nClosed',
        'submission_subject': 'Received', 'submission_email': 'Got {{ticket_type}}',
        'assignment_subject': 'Assigned to you',
        'assignment_email': 'Hi {{first_name}}, a {{ticket_type}} request from '
                            '{{submitter_name}} is yours: {{message}}',
    }
    value.update(overrides)
    Setting.objects.update_or_create(key=STS.key, defaults={'value': value})


def _sent_to(address):
    send_all()
    return [m for m in mail.outbox if address in m.to]


@override_settings(EMAIL_BACKEND=LOCMEM, MAILER_EMAIL_BACKEND=LOCMEM)
class AssigneeEmailTests(TestCase):
    def setUp(self):
        _configure()
        self.submitter = User.objects.create(
            username='stu', email='stu@example.com', first_name='Sam', last_name='Stu')
        self.ce = User.objects.create(
            username='ce', email='ce@example.com', first_name='Cee')
        self.other = User.objects.create(
            username='ce2', email='ce2@example.com', first_name='Otto')
        self.tt = TicketType.objects.create(
            name='Tech', applies_to='Students', assigned_to=self.ce, email_assignee=True)

    def _ticket(self, ticket_type=None):
        return Ticket.objects.create(
            ticket_type=ticket_type or self.tt, submitted_by=self.submitter, message='help me')

    def test_default_assignee_is_emailed_on_submission(self):
        mail.outbox = []
        self._ticket()
        sent = _sent_to('ce@example.com')
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].subject, 'Assigned to you')
        self.assertIn('Hi Cee, a Tech request from Sam Stu is yours: help me', sent[0].body)

    def test_unchecked_type_does_not_email_the_assignee(self):
        self.tt.email_assignee = False
        self.tt.save()
        mail.outbox = []
        t = self._ticket()
        t.assigned_to = self.other
        t.save()
        self.assertEqual(_sent_to('ce@example.com'), [])
        self.assertEqual(_sent_to('ce2@example.com'), [])

    def test_reassignment_emails_the_new_assignee(self):
        t = self._ticket()
        t.refresh_from_db()
        send_all()  # deliver the creation email before clearing
        mail.outbox = []
        t.assigned_to = self.other
        t.save()
        self.assertEqual(len(_sent_to('ce2@example.com')), 1)
        self.assertEqual(_sent_to('ce@example.com'), [])

    def test_saving_without_changing_the_assignee_sends_nothing(self):
        t = self._ticket()
        t.refresh_from_db()
        send_all()  # deliver the creation email before clearing
        mail.outbox = []
        t.status = 'Pending'
        t.save()
        self.assertEqual(_sent_to('ce@example.com'), [])

    def test_unassigning_sends_nothing(self):
        t = self._ticket()
        t.refresh_from_db()
        send_all()  # deliver the creation email before clearing
        mail.outbox = []
        t.assigned_to = None
        t.save()
        send_all()
        self.assertEqual(mail.outbox, [])

    def test_bulk_reassign_emails_the_new_assignee_once_per_changed_ticket(self):
        Group.objects.get_or_create(name='ce')[0].user_set.add(self.other)
        first, second = self._ticket(), self._ticket()
        Ticket.objects.filter(pk=second.pk).update(assigned_to=self.other)
        send_all()
        mail.outbox = []
        form = BulkTicketAssignForm(
            ticket_ids=[str(first.pk), str(second.pk)],
            data={'assigned_to': self.other.pk})
        self.assertTrue(form.is_valid(), form.errors)
        form.save(request=None)
        # `second` already belonged to Otto, so only `first` is a new assignment
        self.assertEqual(len(_sent_to('ce2@example.com')), 1)

    def test_falls_back_to_default_wording_when_settings_predate_the_feature(self):
        value = Setting.objects.get(key=STS.key).value
        del value['assignment_subject'], value['assignment_email']
        Setting.objects.filter(key=STS.key).update(value=value)
        mail.outbox = []
        self._ticket()
        sent = _sent_to('ce@example.com')
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0].subject)
        self.assertIn('Tech', sent[0].body)

    def test_off_switch_sends_nothing(self):
        _configure(is_active='No')
        mail.outbox = []
        self._ticket()
        send_all()
        self.assertEqual(mail.outbox, [])


class TicketTypeFormEmailAssigneeTests(TestCase):
    def test_form_offers_and_saves_the_flag(self):
        form = TicketTypeForm(data={
            'name': 'Transcripts', 'applies_to': 'Students', 'email_assignee': 'on'})
        self.assertIn('email_assignee', form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().email_assignee)

    def test_flag_defaults_off(self):
        tt = TicketType.objects.create(name='Other', applies_to='Students')
        self.assertFalse(tt.email_assignee)
