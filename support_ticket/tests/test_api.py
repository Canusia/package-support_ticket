from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from ..models.ticket import Ticket, TicketType
from ..serializers import TicketSerializer

User = get_user_model()


class TicketSerializerTests(TestCase):
    def test_serializes_expected_fields(self):
        sub = User.objects.create(email='s@example.com', first_name='Sam', last_name='Lee')
        tt = TicketType.objects.create(name='Tech', applies_to='Students')
        t = Ticket.objects.create(ticket_type=tt, submitted_by=sub, message='hi', status='Pending')
        data = TicketSerializer(t, context={'portal_detail_urlname': 'support_ticket:request'}).data
        self.assertEqual(data['ticket_type_name'], 'Tech')
        self.assertEqual(data['submitter_name'], 'Lee, Sam')
        self.assertEqual(data['status'], 'Pending')
        self.assertIn(str(t.id), data['detail_url'])


class TicketScopingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tt = TicketType.objects.create(name='Tech', applies_to='Students')
        self.alice = User.objects.create(username='alice', email='alice@example.com')
        self.bob = User.objects.create(username='bob', email='bob@example.com')
        self.t_alice = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.alice, message='a')
        self.t_bob = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.bob, message='b')

    def _ids(self, resp):
        return {row['id'] for row in resp.json()['data']}

    def _grant(self, user, role):
        grp, _ = Group.objects.get_or_create(name=role)
        user.groups.add(grp)

    def test_student_sees_only_own_tickets(self):
        # give alice the student role (adjust to repo's group/role mechanism)
        from django.contrib.auth.models import Group
        alice_grp, _ = Group.objects.get_or_create(name='student')
        self.alice.groups.add(alice_grp)
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/v1/support-ticket-student/?format=datatables')
        self.assertEqual(resp.status_code, 200)
        ids = self._ids(resp)
        self.assertIn(str(self.t_alice.id), ids)
        self.assertNotIn(str(self.t_bob.id), ids)

    def test_instructor_sees_only_own_tickets(self):
        self._grant(self.alice, 'instructor')
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/v1/support-ticket-instructor/?format=datatables')
        self.assertEqual(resp.status_code, 200)
        ids = self._ids(resp)
        self.assertIn(str(self.t_alice.id), ids)
        self.assertNotIn(str(self.t_bob.id), ids)

    def test_ce_sees_all_tickets(self):
        self._grant(self.alice, 'ce')
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/v1/support-ticket-ce/?format=datatables')
        self.assertEqual(resp.status_code, 200)
        ids = self._ids(resp)
        self.assertIn(str(self.t_alice.id), ids)
        self.assertIn(str(self.t_bob.id), ids)

    def test_student_forbidden_without_role(self):
        self.client.force_authenticate(self.bob)
        resp = self.client.get('/api/v1/support-ticket-student/?format=datatables')
        self.assertEqual(resp.status_code, 403)

    def test_attachment_count_annotated(self):
        self._grant(self.alice, 'student')
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/v1/support-ticket-student/?format=datatables')
        row = next(r for r in resp.json()['data'] if r['id'] == str(self.t_alice.id))
        self.assertEqual(row['attachment_count'], 0)

    def test_student_cannot_retrieve_another_users_ticket_via_api(self):
        """Alice (student) requesting Bob's ticket via the student API detail endpoint -> 404."""
        self._grant(self.alice, 'student')
        self.client.force_authenticate(self.alice)
        resp = self.client.get(
            f'/api/v1/support-ticket-student/{self.t_bob.id}/?format=datatables')
        self.assertEqual(resp.status_code, 404)


class HSAdminTicketScopingTests(TestCase):
    def setUp(self):
        from cis.models.highschool import HighSchool
        from cis.models.student import Student
        from cis.models.highschool_administrator import (
            HSAdministrator, HSAdministratorPosition, HSPosition)

        self.client = APIClient()
        self.tt = TicketType.objects.create(
            name='HS', applies_to='High School Administrators')

        # Student.save() adds the user to the 'student' group, so it must exist
        Group.objects.get_or_create(name='student')

        self.hs_a = HighSchool.objects.create(name='HS A')
        self.hs_b = HighSchool.objects.create(name='HS B')
        self.position = HSPosition.objects.create(name='Principal')

        # admin under HS A
        self.admin_user = User.objects.create(username='admin', email='admin@example.com')
        admin_grp, _ = Group.objects.get_or_create(name='highschool_admin')
        self.admin_user.groups.add(admin_grp)
        self.admin_acct = HSAdministrator.objects.create(user=self.admin_user)
        # status='Active' so the hs_position_updated signal grants the role group
        HSAdministratorPosition.objects.create(
            hsadmin=self.admin_acct, highschool=self.hs_a, position=self.position,
            status='Active')

        # student in HS A -> visible to admin
        self.student_a_user = User.objects.create(username='stu_a', email='stu_a@example.com')
        Student.objects.create(user=self.student_a_user, highschool=self.hs_a)

        # student in HS B -> NOT visible to admin
        self.student_b_user = User.objects.create(username='stu_b', email='stu_b@example.com')
        Student.objects.create(user=self.student_b_user, highschool=self.hs_b)

        # another admin in HS A -> visible to admin
        self.admin2_user = User.objects.create(username='admin2', email='admin2@example.com')
        admin2_acct = HSAdministrator.objects.create(user=self.admin2_user)
        HSAdministratorPosition.objects.create(
            hsadmin=admin2_acct, highschool=self.hs_a, position=self.position,
            status='Active')

        self.t_student_a = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.student_a_user, message='sa')
        self.t_student_b = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.student_b_user, message='sb')
        self.t_admin2 = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.admin2_user, message='a2')

    def _ids(self, resp):
        return {row['id'] for row in resp.json()['data']}

    def test_hsadmin_sees_students_and_admins_of_own_highschools_only(self):
        self.client.force_authenticate(self.admin_user)
        resp = self.client.get('/api/v1/support-ticket-hsadmin/?format=datatables')
        self.assertEqual(resp.status_code, 200)
        ids = self._ids(resp)
        self.assertIn(str(self.t_student_a.id), ids)   # student in own HS
        self.assertIn(str(self.t_admin2.id), ids)      # co-admin in own HS
        self.assertNotIn(str(self.t_student_b.id), ids)  # student in other HS


class StudentAPIIDORTest(TestCase):
    """D3 regression insurance: student detail API must not expose other users' tickets."""

    def setUp(self):
        self.client = APIClient()
        self.tt = TicketType.objects.create(name='IDOR-Tech', applies_to='Students')
        self.alice = User.objects.create(username='idor_alice', email='idor_alice@example.com')
        self.bob = User.objects.create(username='idor_bob', email='idor_bob@example.com')
        grp, _ = Group.objects.get_or_create(name='student')
        self.alice.groups.add(grp)
        self.bob.groups.add(grp)
        self.bob_ticket = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.bob, message='bobs secret')

    def test_student_cannot_access_another_users_ticket_via_api(self):
        """Alice (student) requesting Bob's ticket via student API list must not see it."""
        self.client.force_authenticate(self.alice)
        resp = self.client.get('/api/v1/support-ticket-student/?format=datatables')
        self.assertEqual(resp.status_code, 200)
        ids = {row['id'] for row in resp.json()['data']}
        self.assertNotIn(str(self.bob_ticket.id), ids)


class InstructorPortalTests(TestCase):
    def test_instructor_index_route_resolves(self):
        self.assertTrue(reverse('instructor_support_ticket:requests'))

    def test_instructor_cannot_open_another_users_ticket_detail(self):
        """Instructor requesting a ticket not submitted by them -> 404 (IDOR guard)."""
        instr = User.objects.create(email='instr@example.com', username='instr@example.com')
        instr.groups.add(Group.objects.get_or_create(name='instructor')[0])
        other = User.objects.create(email='other2@example.com', username='other2@example.com')
        tt = TicketType.objects.create(name='X', applies_to='Instructors')
        other_ticket = Ticket.objects.create(ticket_type=tt, submitted_by=other, message='x')
        # Temporarily disconnect django_login_history signal — it requires HTTP headers
        # not present in the Django test client's synthetic login request.
        from django.contrib.auth.signals import user_logged_in
        from django_login_history.models import post_login
        user_logged_in.disconnect(post_login)
        try:
            c = Client()
            c.force_login(instr)
        finally:
            user_logged_in.connect(post_login)
        resp = c.get(reverse('instructor_support_ticket:details', args=[str(other_ticket.id)]))
        self.assertEqual(resp.status_code, 404)


class CETicketFilterTests(TestCase):
    """Part A: CETicketViewSet filter tests — status, assigned_to, unassigned, bad UUID."""

    def setUp(self):
        self.client = APIClient()
        self.tt = TicketType.objects.create(name='FilterType', applies_to='Students')
        # CE user (authenticated for all CE-scoped requests)
        self.ce = User.objects.create(username='ce_filter', email='ce_filter@example.com')
        self.ce.groups.add(Group.objects.get_or_create(name='ce')[0])
        # Second CE user for assigned_to filter
        self.ce2 = User.objects.create(username='ce_filter2', email='ce_filter2@example.com')
        self.ce2.groups.add(Group.objects.get_or_create(name='ce')[0])

        self.t_open = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.ce2,
            message='open', status='Open', assigned_to=self.ce)
        self.t_closed = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.ce2,
            message='closed', status='Closed', assigned_to=self.ce2)
        self.t_unassigned = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.ce2,
            message='unassigned', status='Open', assigned_to=None)

    def _ids(self, resp):
        return {row['id'] for row in resp.json()['data']}

    def _get(self, params):
        self.client.force_authenticate(self.ce)
        return self.client.get('/api/v1/support-ticket-ce/', data={**params, 'format': 'datatables'})

    def test_ce_filter_by_status(self):
        resp = self._get({'status': 'Closed'})
        self.assertEqual(resp.status_code, 200)
        ids = self._ids(resp)
        self.assertIn(str(self.t_closed.id), ids)
        self.assertNotIn(str(self.t_open.id), ids)
        self.assertNotIn(str(self.t_unassigned.id), ids)

    def test_ce_filter_by_assigned_to(self):
        resp = self._get({'assigned_to': str(self.ce.id)})
        self.assertEqual(resp.status_code, 200)
        ids = self._ids(resp)
        self.assertIn(str(self.t_open.id), ids)
        self.assertNotIn(str(self.t_closed.id), ids)
        self.assertNotIn(str(self.t_unassigned.id), ids)

    def test_ce_filter_unassigned(self):
        resp = self._get({'assigned_to': 'unassigned'})
        self.assertEqual(resp.status_code, 200)
        ids = self._ids(resp)
        self.assertIn(str(self.t_unassigned.id), ids)
        self.assertNotIn(str(self.t_open.id), ids)
        self.assertNotIn(str(self.t_closed.id), ids)

    def test_ce_filter_bad_assigned_to_uuid_no_500(self):
        resp = self._get({'assigned_to': 'not-a-uuid'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    def test_ce_index_context_has_filter_options(self):
        """Part B: index view must include statuses and ce_users in context."""
        from django.contrib.auth.signals import user_logged_in
        from django_login_history.models import post_login
        user_logged_in.disconnect(post_login)
        try:
            c = Client()
            c.force_login(self.ce)
        finally:
            user_logged_in.connect(post_login)
        resp = c.get(reverse('support_ticket:requests'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('statuses', resp.context)
        self.assertIn('ce_users', resp.context)


class IndexViewShapeTests(TestCase):
    """D5: index views must pass api_url to context and NOT pass records."""

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

    def test_ce_index_context_has_api_url_not_records(self):
        ce = User.objects.create(email='ce_idx@example.com', username='ce_idx@example.com')
        ce.groups.add(Group.objects.get_or_create(name='ce')[0])
        c = self._login(ce)
        resp = c.get(reverse('support_ticket:requests'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('api_url', resp.context)
        self.assertNotIn('records', resp.context)

    def test_student_index_context_has_api_url_not_records(self):
        student = User.objects.create(
            email='student_idx@example.com', username='student_idx@example.com')
        student.groups.add(Group.objects.get_or_create(name='student')[0])
        c = self._login(student)
        resp = c.get(reverse('student_support_ticket:requests'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('api_url', resp.context)
        self.assertNotIn('records', resp.context)

    def test_instructor_index_context_has_api_url_not_records(self):
        instr = User.objects.create(
            email='instr_idx@example.com', username='instr_idx@example.com')
        instr.groups.add(Group.objects.get_or_create(name='instructor')[0])
        c = self._login(instr)
        resp = c.get(reverse('instructor_support_ticket:requests'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('api_url', resp.context)
        self.assertNotIn('records', resp.context)

    def test_hs_admin_index_context_has_api_url_not_records(self):
        hs_admin = User.objects.create(
            email='hsadmin_idx@example.com', username='hsadmin_idx@example.com')
        hs_admin.groups.add(Group.objects.get_or_create(name='highschool_admin')[0])
        c = self._login(hs_admin)
        resp = c.get(reverse('hs_admin_support_ticket:requests'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('api_url', resp.context)
        self.assertNotIn('records', resp.context)
