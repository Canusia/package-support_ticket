"""
Tests for CE bulk actions on support tickets.

Covers:
  - bulk_update_status  Phase 1: returns outcome='modal' with status form
  - bulk_update_status  Phase 2: updates tickets + returns success call
  - bulk_update_assigned_to Phase 2: reassigns tickets + returns success
  - CE-only gate: non-CE user -> redirect to '/'
  - Invalid form input -> 400 with errors, no mutation
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from ..models.ticket import Ticket, TicketType

User = get_user_model()

BULK_URL = 'support_ticket:bulk_actions'


def _login(user):
    """
    Force-login via Django test Client, neutralising the login-history signal
    (django_login_history.post_login crashes when REMOTE_ADDR is absent in
    test requests).
    """
    from django.contrib.auth.signals import user_logged_in
    from django_login_history.models import post_login
    user_logged_in.disconnect(post_login)
    try:
        c = Client()
        c.force_login(user)
    finally:
        user_logged_in.connect(post_login)
    return c


def _make_group(name):
    grp, _ = Group.objects.get_or_create(name=name)
    return grp


class BulkActionAuthTests(TestCase):
    """Gate: only CE users may call the endpoint."""

    def setUp(self):
        self.tt = TicketType.objects.create(name='Auth', applies_to='Students')
        self.submitter = User.objects.create(
            email='submitter_auth@example.com',
            username='submitter_auth@example.com',
        )
        self.ticket = Ticket.objects.create(
            ticket_type=self.tt,
            submitted_by=self.submitter,
            message='test',
            status='Submitted',
        )

    def test_non_ce_user_is_redirected(self):
        student = User.objects.create(
            email='student_ba@example.com',
            username='student_ba@example.com',
        )
        student.groups.add(_make_group('student'))
        c = _login(student)
        resp = c.post(
            reverse(BULK_URL),
            {'action': 'bulk_update_status', 'ids[]': [str(self.ticket.id)]},
        )
        # user_passes_test redirects to '/'
        self.assertIn(resp.status_code, [302, 403])
        if resp.status_code == 302:
            self.assertIn('/', resp['Location'])
        # No mutation
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'Submitted')

    def test_anonymous_user_is_redirected(self):
        c = Client()
        resp = c.post(
            reverse(BULK_URL),
            {'action': 'bulk_update_status', 'ids[]': [str(self.ticket.id)]},
        )
        self.assertIn(resp.status_code, [302, 403])


class BulkUpdateStatusTests(TestCase):
    """Two-phase bulk_update_status handler."""

    def setUp(self):
        self.ce = User.objects.create(
            email='ce_bulk_st@example.com',
            username='ce_bulk_st@example.com',
            is_active=True,
        )
        self.ce.groups.add(_make_group('ce'))
        self.submitter = User.objects.create(
            email='sub_bulk_st@example.com',
            username='sub_bulk_st@example.com',
        )
        self.tt = TicketType.objects.create(name='Status', applies_to='Students')
        self.t1 = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.submitter,
            message='m1', status='Submitted',
        )
        self.t2 = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.submitter,
            message='m2', status='Submitted',
        )

    def test_phase1_returns_modal_with_status_field(self):
        """First POST (no action_confirmed) -> outcome='modal', html contains status field."""
        c = _login(self.ce)
        resp = c.post(
            reverse(BULK_URL),
            {
                'action': 'bulk_update_status',
                'ids[]': [str(self.t1.id), str(self.t2.id)],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['outcome'], 'modal')
        self.assertIn('html', data)
        self.assertIn('id_status', data['html'])

    def test_phase2_updates_status_and_returns_call(self):
        """Second POST (action_confirmed=1) -> tickets updated, outcome='call'."""
        c = _login(self.ce)
        resp = c.post(
            reverse(BULK_URL),
            {
                'action': 'bulk_update_status',
                'action_confirmed': '1',
                'status': 'Pending',
                'ids[]': [str(self.t1.id), str(self.t2.id)],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['outcome'], 'call')
        self.assertEqual(data['fn'], 'refreshTable')
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertEqual(self.t1.status, 'Pending')
        self.assertEqual(self.t2.status, 'Pending')

    def test_phase2_invalid_status_returns_400(self):
        """Phase 2 with an invalid status -> 400, no mutation."""
        c = _login(self.ce)
        resp = c.post(
            reverse(BULK_URL),
            {
                'action': 'bulk_update_status',
                'action_confirmed': '1',
                'status': 'NOT_A_REAL_STATUS_XYZ',
                'ids[]': [str(self.t1.id)],
            },
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn('errors', data)
        self.t1.refresh_from_db()
        self.assertEqual(self.t1.status, 'Submitted')


class BulkUpdateAssignedToTests(TestCase):
    """Two-phase bulk_update_assigned_to handler."""

    def setUp(self):
        self.ce = User.objects.create(
            email='ce_bulk_at@example.com',
            username='ce_bulk_at@example.com',
            is_active=True,
        )
        self.ce.groups.add(_make_group('ce'))
        self.ce_assignee = User.objects.create(
            email='ce_assignee@example.com',
            username='ce_assignee@example.com',
            is_active=True,
        )
        self.ce_assignee.groups.add(_make_group('ce'))
        self.submitter = User.objects.create(
            email='sub_bulk_at@example.com',
            username='sub_bulk_at@example.com',
        )
        self.tt = TicketType.objects.create(name='Assign', applies_to='Students')
        self.t1 = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.submitter,
            message='m1', status='Submitted',
        )
        self.t2 = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.submitter,
            message='m2', status='Submitted',
        )

    def test_phase1_returns_modal_with_assigned_to_field(self):
        c = _login(self.ce)
        resp = c.post(
            reverse(BULK_URL),
            {
                'action': 'bulk_update_assigned_to',
                'ids[]': [str(self.t1.id)],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['outcome'], 'modal')
        self.assertIn('id_assigned_to', data['html'])

    def test_phase2_reassigns_tickets(self):
        c = _login(self.ce)
        resp = c.post(
            reverse(BULK_URL),
            {
                'action': 'bulk_update_assigned_to',
                'action_confirmed': '1',
                'assigned_to': str(self.ce_assignee.pk),
                'ids[]': [str(self.t1.id), str(self.t2.id)],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['outcome'], 'call')
        self.assertEqual(data['fn'], 'refreshTable')
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertEqual(self.t1.assigned_to_id, self.ce_assignee.pk)
        self.assertEqual(self.t2.assigned_to_id, self.ce_assignee.pk)

    def test_phase2_invalid_assignee_returns_400(self):
        """Phase 2 with a non-existent/non-CE user -> 400, no mutation."""
        c = _login(self.ce)
        # user pk 999999 does not exist
        resp = c.post(
            reverse(BULK_URL),
            {
                'action': 'bulk_update_assigned_to',
                'action_confirmed': '1',
                'assigned_to': '999999',
                'ids[]': [str(self.t1.id)],
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('errors', resp.json())
        self.t1.refresh_from_db()
        self.assertIsNone(self.t1.assigned_to_id)


class BulkUUIDGuardTests(TestCase):
    """Bug #7: malformed id in ticket_ids must not raise ValidationError / 500."""

    def setUp(self):
        from cis.models.settings import Setting
        from ..settings.support_ticket_settings import support_ticket_settings as STS
        Setting.objects.update_or_create(
            key=STS.key,
            defaults={'value': {'statuses': 'Submitted\nPending\nClosed'}},
        )
        self.ce = User.objects.create(
            email='ce_uuid_g@example.com',
            username='ce_uuid_g@example.com',
            is_active=True,
        )
        self.ce.groups.add(_make_group('ce'))
        self.submitter = User.objects.create(
            email='sub_uuid_g@example.com',
            username='sub_uuid_g@example.com',
        )
        self.tt = TicketType.objects.create(name='UUID Guard', applies_to='Students')
        self.ticket = Ticket.objects.create(
            ticket_type=self.tt,
            submitted_by=self.submitter,
            message='test',
            status='Submitted',
        )

    def test_status_form_ignores_invalid_uuid(self):
        """BulkTicketStatusForm with mixed ids: only real ticket updated, no exception."""
        from ..forms.bulk import BulkTicketStatusForm
        form = BulkTicketStatusForm(
            ticket_ids=['not-a-uuid', 'BAD', str(self.ticket.id)],
            data={'status': 'Pending'},
        )
        self.assertTrue(form.is_valid(), form.errors)
        count = form.save(None)
        self.assertEqual(count, 1)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'Pending')

    def test_assign_form_ignores_invalid_uuid(self):
        """BulkTicketAssignForm with mixed ids: only real ticket updated, no exception."""
        from ..forms.bulk import BulkTicketAssignForm
        form = BulkTicketAssignForm(
            ticket_ids=['not-a-uuid', '12345', str(self.ticket.id)],
            data={'assigned_to': str(self.ce.pk)},
        )
        self.assertTrue(form.is_valid(), form.errors)
        count = form.save(None)
        self.assertEqual(count, 1)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_to_id, self.ce.pk)

    def test_bulk_endpoint_with_bad_uuid_returns_200_not_500(self):
        """POST to bulk endpoint with a malformed id must not 500."""
        c = _login(self.ce)
        resp = c.post(
            reverse(BULK_URL),
            {
                'action': 'bulk_update_status',
                'action_confirmed': '1',
                'status': 'Pending',
                'ids[]': ['not-a-uuid', str(self.ticket.id)],
            },
        )
        self.assertNotEqual(resp.status_code, 500)
        self.assertEqual(resp.status_code, 200)
