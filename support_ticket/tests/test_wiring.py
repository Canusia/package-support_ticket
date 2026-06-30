from django.apps import apps
from django.test import TestCase
from django.urls import reverse


class AppWiringTests(TestCase):
    def test_app_label_is_support_ticket(self):
        self.assertEqual(apps.get_app_config('support_ticket').label, 'support_ticket')

    def test_models_importable(self):
        from support_ticket.models.ticket import Ticket, TicketType, TicketNote  # noqa: F401

    def test_url_namespaces_resolve(self):
        # one URL per portal namespace proves urls/*.py are wired
        self.assertTrue(reverse('support_ticket:requests'))
        self.assertTrue(reverse('student_support_ticket:requests'))
        self.assertTrue(reverse('hs_admin_support_ticket:requests'))
