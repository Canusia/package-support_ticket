"""Term on tickets, opt-out note emails with a sent record, and the CE list/type pages.

- New tickets default to the active term; CE can change it on the detail page.
- The CE note form has "Email this note to the submitter" (checked by default);
  every note records who it was actually emailed to and when.
- The CE requests list and the type detail page share one filtered table.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from mailer.engine import send_all

from cis.models.settings import Setting
from cis.models.term import AcademicYear, Term
from ..models.ticket import Ticket, TicketNote, TicketType
from ..services import add_note_with_files
from ..settings.support_ticket_settings import support_ticket_settings as STS

User = get_user_model()
LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def _login(user):
    from django.contrib.auth.signals import user_logged_in
    from django_login_history.models import post_login
    user_logged_in.disconnect(post_login)
    try:
        c = Client()
        c.force_login(user)
    finally:
        user_logged_in.connect(post_login)
    return c


def _set_active_term(term):
    key = getattr(settings, 'CAMPUS_CODE_PREFIX') + '_cis_registrations'
    Setting.objects.update_or_create(key=key, defaults={'value': {'active_term': str(term.id)}})


class _Fixture(TestCase):
    def setUp(self):
        Setting.objects.update_or_create(key=STS.key, defaults={'value': {
            'is_active': 'Yes', 'from_email': 'support@example.com',
            'statuses': 'Submitted\nPending\nClosed',
            'note_subject': 'Note', 'note_email': '{{update}}',
        }})
        ay = AcademicYear.objects.create(name='2026-2027')
        self.fall = Term.objects.create(academic_year=ay, label='Fall', code='F26')
        self.spring = Term.objects.create(academic_year=ay, label='Spring', code='S27')
        _set_active_term(self.fall)

        self.submitter = User.objects.create(
            username='stu', email='stu@example.com', first_name='Sam', last_name='Stu')
        self.assignee = User.objects.create(
            username='asg', email='asg@example.com', first_name='Ann', last_name='Asg')
        self.ce = User.objects.create_superuser(
            username='ce_other', email='ce_other@example.com', password='x')
        ce_group = Group.objects.get_or_create(name='ce')[0]
        self.ce.groups.add(ce_group)
        self.assignee.groups.add(ce_group)

        self.tech = TicketType.objects.create(name='Tech', applies_to='Students')
        self.billing = TicketType.objects.create(name='Billing', applies_to='Students')
        self.ticket = Ticket.objects.create(
            ticket_type=self.tech, submitted_by=self.submitter,
            assigned_to=self.assignee, message='help')


class TicketTermTests(_Fixture):
    def test_new_ticket_defaults_to_the_active_term(self):
        self.assertEqual(self.ticket.term, self.fall)

    def test_an_explicit_term_is_kept(self):
        t = Ticket.objects.create(
            ticket_type=self.tech, submitted_by=self.submitter, message='x', term=self.spring)
        self.assertEqual(t.term, self.spring)

    def test_ticket_is_still_created_when_the_active_term_cannot_be_resolved(self):
        with override_settings():
            del settings.CAMPUS_CODE_PREFIX
            t = Ticket.objects.create(
                ticket_type=self.tech, submitted_by=self.submitter, message='x')
        self.assertIsNone(t.term)

    def test_ce_can_change_the_term_on_the_detail_page(self):
        c = _login(self.ce)
        resp = c.post(reverse('support_ticket:request', args=[self.ticket.id]), {
            'assigned_to': self.assignee.pk, 'status': 'Pending', 'term': self.spring.pk,
        })
        self.assertEqual(resp.status_code, 302)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.term, self.spring)


@override_settings(EMAIL_BACKEND=LOCMEM, MAILER_EMAIL_BACKEND=LOCMEM)
class NoteEmailTests(_Fixture):
    def _flush(self):
        send_all()
        mail.outbox = []

    def _to(self, address):
        send_all()
        return [m for m in mail.outbox if address in m.to]

    def test_note_by_assignee_emails_submitter_and_records_it(self):
        self._flush()
        note = add_note_with_files(self.assignee, self.ticket, 'fixed', 'Public', [])
        self.assertEqual(len(self._to('stu@example.com')), 1)
        note.refresh_from_db()
        self.assertEqual(note.emailed_to, 'stu@example.com')
        self.assertIsNotNone(note.emailed_on)

    def test_unticked_note_by_assignee_emails_nobody(self):
        self._flush()
        note = add_note_with_files(
            self.assignee, self.ticket, 'quiet', 'Public', [], email_submitter=False)
        send_all()
        self.assertEqual(mail.outbox, [])
        note.refresh_from_db()
        self.assertEqual(note.emailed_to, '')
        self.assertIsNone(note.emailed_on)

    def test_unticked_note_by_third_party_still_emails_the_assignee(self):
        self._flush()
        note = add_note_with_files(
            self.ce, self.ticket, 'fyi', 'Public', [], email_submitter=False)
        self.assertEqual(self._to('stu@example.com'), [])
        self.assertEqual(len(self._to('asg@example.com')), 1)
        note.refresh_from_db()
        self.assertEqual(note.emailed_to, 'asg@example.com')

    def test_submitter_note_records_the_assignee(self):
        self._flush()
        note = add_note_with_files(self.submitter, self.ticket, 'thanks', 'Public', [])
        note.refresh_from_db()
        self.assertEqual(note.emailed_to, 'asg@example.com')

    def test_nothing_recorded_when_email_is_off(self):
        value = Setting.objects.get(key=STS.key).value
        value['is_active'] = 'No'
        Setting.objects.filter(key=STS.key).update(value=value)
        note = add_note_with_files(self.assignee, self.ticket, 'x', 'Public', [])
        note.refresh_from_db()
        self.assertEqual(note.emailed_to, '')
        self.assertIsNone(note.emailed_on)

    def test_ce_form_checkbox_is_ticked_by_default_and_honoured(self):
        c = _login(self.assignee)
        url = reverse('support_ticket:request', args=[self.ticket.id])
        page = c.get(url).content.decode()
        self.assertIn('name="email_submitter"', page)
        self.assertRegex(page, r'name="email_submitter"[^>]*checked')
        self._flush()
        # an unticked checkbox is simply absent from the POST
        c.post(url, {'note': 'no email please', 'add_note': 'Add Note',
                     'model': 'ticketnote', 'ajax': 0, 'add_to': self.ticket.id, 'id': -1})
        send_all()
        self.assertEqual([m for m in mail.outbox if 'stu@example.com' in m.to], [])
        self.assertTrue(TicketNote.objects.filter(note='no email please').exists())

    def test_updates_table_shows_empty_state_and_sent_status(self):
        c = _login(self.ce)
        url = reverse('support_ticket:request', args=[self.ticket.id])
        self.assertIn('No updates found', c.get(url).content.decode())

        add_note_with_files(self.assignee, self.ticket, 'sent one', 'Public', [])
        add_note_with_files(
            self.assignee, self.ticket, 'quiet one', 'Public', [], email_submitter=False)
        page = c.get(url).content.decode()
        self.assertNotIn('No updates found', page)
        self.assertIn('Emailed to stu@example.com', page)
        self.assertIn('Not emailed', page)


class CEListAndTypeTableTests(_Fixture):
    def setUp(self):
        super().setUp()
        Ticket.objects.create(
            ticket_type=self.billing, submitted_by=self.submitter, message='$', term=self.spring)
        self.client = _login(self.ce)
        self.api = reverse('support-ticket-ce-list')

    def _ids(self, **params):
        resp = self.client.get(self.api, {'format': 'json', **params})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        rows = data['results'] if isinstance(data, dict) else data
        return rows

    def test_filters_by_type_and_term_and_reports_the_term(self):
        rows = self._ids(ticket_type=str(self.billing.id))
        self.assertEqual({r['ticket_type_name'] for r in rows}, {'Billing'})
        self.assertEqual(rows[0]['term_label'], str(self.spring))

        rows = self._ids(term_id=str(self.fall.id))
        self.assertEqual({r['ticket_type_name'] for r in rows}, {'Tech'})

    def test_bad_filter_values_return_nothing_not_500(self):
        self.assertEqual(self._ids(ticket_type='nope'), [])
        self.assertEqual(self._ids(term_id='nope'), [])
        self.assertEqual(self._ids(submitted_from='not-a-date'), [])

    def test_date_range_filter(self):
        self.assertEqual(len(self._ids(submitted_from='2000-01-01')), 2)
        self.assertEqual(self._ids(submitted_until='2000-01-01'), [])

    def test_index_page_has_the_filter_card_and_no_null_data_column(self):
        page = self.client.get(reverse('support_ticket:requests')).content.decode()
        for name in ('status', 'assigned_to', 'ticket_type', 'term_id',
                     'submitted_from', 'submitted_until'):
            self.assertIn(f'name="{name}"', page)
        self.assertIn('Filter & Get Results', page)
        self.assertNotIn('data: null', page)

    def test_type_detail_page_shows_that_types_tickets(self):
        page = self.client.get(
            reverse('support_ticket:type', args=[self.billing.id])).content.decode()
        # api_url is escapejs'd into the script, so compare against escapejs' output
        from django.utils.html import escapejs
        self.assertIn('support_type_requests_table', page)
        self.assertIn(escapejs(f'&ticket_type={self.billing.id}'), page)
        self.assertNotIn('name="ticket_type"', page)  # fixed, not a filter
