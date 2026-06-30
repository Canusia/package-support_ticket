from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from ..models.ticket import Ticket, TicketType

User = get_user_model()


class SummaryViewSetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.ce = User.objects.create(username='ce_summary', email='ce@example.com')
        self.ce.groups.add(Group.objects.get_or_create(name='ce')[0])
        self.client.force_authenticate(self.ce)
        self.sub = User.objects.create(username='sub_summary', email='s@example.com')
        tt = TicketType.objects.create(name='Tech', applies_to='Students')
        Ticket.objects.create(ticket_type=tt, submitted_by=self.sub, status='Submitted')
        Ticket.objects.create(ticket_type=tt, submitted_by=self.sub, status='Submitted')
        Ticket.objects.create(ticket_type=tt, submitted_by=self.sub, status='Closed')

    def test_group_by_status_counts(self):
        resp = self.client.get(
            '/api/v1/support-ticket-summary/?group_by=status&format=datatables')
        self.assertEqual(resp.status_code, 200)
        rows = {r['group']: r['count'] for r in resp.json()['data']}
        self.assertEqual(rows['Submitted'], 2)
        self.assertEqual(rows['Closed'], 1)

    def test_non_ce_user_denied_summary(self):
        """Security regression: non-CE authenticated users must be denied the summary endpoint.

        TicketSummaryViewSet.get_queryset is intentionally unscoped (CE staff see all
        tickets). The CE-only gate (permission_classes=[CIS_user_only]) must remain in
        place so that students, instructors, and hs-admins cannot see aggregate counts
        across all users' tickets. This test locks in that gate.
        """
        student = User.objects.create(email='stu_sum@example.com', username='stu_sum')
        student.groups.add(Group.objects.get_or_create(name='student')[0])
        self.client.force_authenticate(student)
        resp = self.client.get('/api/v1/support-ticket-summary/?group_by=status&format=datatables')
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_user_denied_summary(self):
        """Security regression: unauthenticated requests must not return 200 on the summary endpoint."""
        self.client.force_authenticate(None)
        resp = self.client.get('/api/v1/support-ticket-summary/?group_by=status&format=datatables')
        self.assertIn(resp.status_code, (401, 403),
                      f"Expected 401 or 403 for anonymous request, got {resp.status_code}")

    def test_detail_route_does_not_exist(self):
        """Regression: TicketSummaryViewSet is list-only; the detail route must not be registered.

        Hitting /api/v1/support-ticket-summary/<pk>/ must return 404 (no route), not a
        misleading aggregate row with count=1.
        """
        import uuid
        fake_pk = uuid.uuid4()
        resp = self.client.get(f'/api/v1/support-ticket-summary/{fake_pk}/')
        self.assertEqual(resp.status_code, 404,
                         f"Expected 404 (no detail route), got {resp.status_code}")


class SummaryPageTests(TestCase):
    def _login(self, user):
        """force_login via Django test Client, neutralising the login-history signal."""
        from django.contrib.auth.signals import user_logged_in
        from django_login_history.models import post_login
        user_logged_in.disconnect(post_login)
        try:
            c = Client()
            c.force_login(user)
        finally:
            user_logged_in.connect(post_login)
        return c

    def test_summary_page_renders_for_ce(self):
        ce = User.objects.create(username='ce2_summary', email='ce2@example.com')
        ce.groups.add(Group.objects.get_or_create(name='ce')[0])
        c = self._login(ce)
        resp = c.get(reverse('support_ticket:summary'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['summary_url_base'], '/api/v1/support-ticket-summary/')
