"""
Regression: every CE support page highlights its own sidebar item.

`cis.menu.draw_menu(menu, active_menu, active_submenu, role_name)` marks an item
active by exact name. The CE "Support Requests" entry, seeded by cis
(`cis.settings.menu.install()` and migration 0064), is named `support_reqs`
with sub-items `all_requests`, `summary` and `types`. The views passed
`manage_types`, `requests` and, on the type detail page, parent
`support_ticket`, so nothing highlighted there.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from ..models.ticket import Ticket, TicketType

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


class CESupportMenuActiveTests(TestCase):
    def setUp(self):
        from cis.settings.menu import menu
        from django.test import RequestFactory
        menu(request=RequestFactory().get("/")).install()

        ce = User.objects.create_superuser(
            username='ce_menu', email='ce_menu@example.com', password='x')
        ce.groups.add(Group.objects.get_or_create(name='ce')[0])
        self.client = _login(ce)

        student = User.objects.create(username='stu_menu', email='stu_menu@example.com')
        self.ticket_type = TicketType.objects.create(name='Tech', applies_to='Students')
        self.ticket = Ticket.objects.create(
            ticket_type=self.ticket_type, submitted_by=student, message='help')

    def _assert_active(self, url, sub_item_url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        body = resp.content.decode()
        # the Support Requests group is expanded ...
        self.assertIn("id='collapsesupport_reqs' class='collapse show'", body, url)
        # ... and exactly the right sub-item is highlighted
        self.assertIn(f"class='collapse-item active' href='{sub_item_url}'", body, url)
        self.assertEqual(body.count("class='collapse-item active'"), 1, url)

    def test_all_requests_pages(self):
        requests_url = reverse('support_ticket:requests')
        self._assert_active(requests_url, requests_url)
        self._assert_active(
            reverse('support_ticket:request', args=[self.ticket.id]), requests_url)

    def test_summary_page(self):
        summary_url = reverse('support_ticket:summary')
        self._assert_active(summary_url, summary_url)

    def test_manage_types_pages(self):
        types_url = reverse('support_ticket:types')
        self._assert_active(types_url, types_url)
        self._assert_active(reverse('support_ticket:add_new_type'), types_url)
        self._assert_active(
            reverse('support_ticket:type', args=[self.ticket_type.id]), types_url)
