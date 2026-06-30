import os
from django.apps import AppConfig


class SupportTicketConfig(AppConfig):
    """Production config — pip-installed as top-level `support_ticket`."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'support_ticket'
    label = 'support_ticket'
    verbose_name = 'Support Tickets'
    path = os.path.dirname(os.path.abspath(__file__))

    CONFIGURATORS = [
        {
            'app': 'support_ticket',
            'name': 'support_ticket_settings',
            'title': 'Support Ticket Settings',
            'description': 'Statuses, who can start tickets, and email templates.',
            'categories': ['4'],
        },
    ]

    REPORTS = [
        {
            'app': 'support_ticket',
            'name': 'ticket_types_export',
            'title': 'Support Ticket Types - Export',
            'description': 'Export all support ticket types with assignment and notify info.',
            'categories': ['4'],
            'available_for': ['ce'],
        },
    ]

    def ready(self):
        # Signals live in support_ticket.signals (prod). Import unconditionally so
        # any error inside the module surfaces loudly rather than being swallowed.
        from . import signals  # noqa: F401


class DevSupportTicketConfig(SupportTicketConfig):
    """Development config — in-tree submodule at support_ticket.support_ticket."""
    name = 'support_ticket.support_ticket'
    label = 'support_ticket'
    verbose_name = 'Dev - Support Tickets'

    CONFIGURATORS = [
        {
            'app': 'support_ticket.support_ticket',
            'name': 'support_ticket_settings',
            'title': 'Support Ticket Settings',
            'description': 'Statuses, who can start tickets, and email templates.',
            'categories': ['4'],
        },
    ]

    REPORTS = [
        {
            'app': 'support_ticket.support_ticket',
            'name': 'ticket_types_export',
            'title': 'Support Ticket Types - Export',
            'description': 'Export all support ticket types with assignment and notify info.',
            'categories': ['4'],
            'available_for': ['ce'],
        },
    ]

    def ready(self):
        # Dev mode: signals live in the in-tree inner package. Import unconditionally
        # so any error inside the module surfaces loudly rather than being swallowed.
        from . import signals  # noqa: F401
