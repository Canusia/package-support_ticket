"""
    Support Ticket CE URL Configuration
"""
from django.contrib.auth.decorators import user_passes_test
from django.urls import path

from cis.utils import user_has_cis_role
from support_ticket.views import types, tickets

app_name = 'support_ticket'
urlpatterns = [
    path('types/', types.index, name='types'),
    path('types/add_new', types.add_new, name='add_new_type'),
    path('types/delete/<uuid:record_id>', types.delete, name='delete_type'),
    path('type/<uuid:record_id>', types.detail, name='type'),

    path('', tickets.index, name='requests'),
    path('request/<uuid:record_id>', tickets.detail, name='request'),
    path('request/delete/<uuid:record_id>', tickets.delete, name='delete_request'),
    path('summary/', tickets.summary, name='summary'),
    path(
        'bulk_actions',
        user_passes_test(user_has_cis_role, login_url='/')(tickets.support_ticket_bulk_actions),
        name='bulk_actions',
    ),
]
