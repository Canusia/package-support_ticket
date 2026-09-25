"""CE request-type pages follow the CE list/detail designs.

- Types list: like the requests list (Actions dropdown, tabbed bordered pane,
  grey filter card, DataTable).
- Type detail: like the student detail page (breadcrumb, Actions dropdown,
  nav-tabs with "<type> Requests" and "Details" panes in card border-top-0).
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from ..models.ticket import TicketType

User = get_user_model()


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


class TypePagesLayoutTests(TestCase):
    def setUp(self):
        ce = User.objects.create_superuser(
            username='ce_types', email='ce_types@example.com', password='x')
        ce.groups.add(Group.objects.get_or_create(name='ce')[0])
        self.client = _login(ce)
        self.tech = TicketType.objects.create(
            name='Tech', applies_to='Students', email_assignee=True)
        TicketType.objects.create(name='Billing', applies_to='Instructors')

    def test_types_list_matches_the_requests_list_design(self):
        page = self.client.get(reverse('support_ticket:types')).content.decode()
        self.assertIn('dropdown-toggle', page)                       # Actions dropdown
        self.assertIn(reverse('support_ticket:add_new_type'), page)
        self.assertIn('bg-white border border-top-0', page)          # tabbed pane
        self.assertIn('card-body bg-gray-200', page)                 # filter card
        self.assertIn('id="request_types_table"', page)
        self.assertIn('name="applies_to"', page)
        for name in ('Tech', 'Billing'):
            self.assertIn(name, page)
        self.assertIn(reverse('support_ticket:type', args=[self.tech.id]), page)

    def test_type_detail_is_tabbed_like_the_student_page(self):
        page = self.client.get(
            reverse('support_ticket:type', args=[self.tech.id])).content.decode()
        self.assertIn('class="nav nav-tabs"', page)
        self.assertIn('href="#requests"', page)
        self.assertIn('Tech Requests', page)
        self.assertIn('href="#details"', page)
        self.assertEqual(page.count('class="card border-top-0"'), 2)
        self.assertIn('support_type_requests_table', page)   # requests pane
        self.assertIn('name="email_assignee"', page)         # details pane form
        self.assertIn(reverse('support_ticket:delete_type', args=[self.tech.id]), page)

    def test_saving_details_returns_to_the_details_tab(self):
        resp = self.client.post(reverse('support_ticket:type', args=[self.tech.id]), {
            'name': 'Tech Help', 'applies_to': 'Students',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp['Location'].endswith('#details'))
