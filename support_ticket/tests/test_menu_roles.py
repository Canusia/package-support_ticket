"""
Regression: each role-portal support page must render ITS OWN sidebar, not the
CE sidebar. `cis.menu.draw_menu` ignores its first arg and picks the sidebar by
the `role_name` (4th) argument, defaulting to 'ce'. These tests spy on draw_menu
and assert the index view of each portal passes the correct role_name.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

# Relative import, not a 'support_ticket.support_ticket.…' string: that path only
# exists when the package is an in-tree submodule, not when pip-installed (#3).
from ..views import highschool_admins, instructors, students

User = get_user_model()


def _login(user):
    """force_login via test Client, neutralising the login-history signal."""
    from django.contrib.auth.signals import user_logged_in
    from django_login_history.models import post_login
    user_logged_in.disconnect(post_login)
    try:
        c = Client()
        c.force_login(user)
    finally:
        user_logged_in.connect(post_login)
    return c


def _roled_user(email, role):
    u = User.objects.create(email=email, username=email)
    u.groups.add(Group.objects.get_or_create(name=role)[0])
    return u


def _role_arg(mock):
    """Extract the role_name draw_menu was called with (4th positional or kwarg)."""
    args, kwargs = mock.call_args
    return args[3] if len(args) > 3 else kwargs.get('role_name')


class SupportTicketMenuRoleTests(TestCase):

    def test_hsadmin_index_passes_highschool_admin_role(self):
        user = _roled_user('hsa_menu@example.com', 'highschool_admin')
        c = _login(user)
        with patch.object(highschool_admins, 'draw_menu',
                   return_value='') as m:
            resp = c.get(reverse('hs_admin_support_ticket:requests'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(m.called)
        self.assertEqual(_role_arg(m), 'highschool_admin')

    def test_student_index_passes_student_role(self):
        user = _roled_user('stu_menu@example.com', 'student')
        c = _login(user)
        with patch.object(students, 'draw_menu',
                   return_value='') as m:
            resp = c.get(reverse('student_support_ticket:requests'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(m.called)
        self.assertEqual(_role_arg(m), 'student')

    def test_instructor_index_passes_instructor_role(self):
        user = _roled_user('ins_menu@example.com', 'instructor')
        c = _login(user)
        with patch.object(instructors, 'draw_menu',
                   return_value='') as m:
            resp = c.get(reverse('instructor_support_ticket:requests'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(m.called)
        self.assertEqual(_role_arg(m), 'instructor')
