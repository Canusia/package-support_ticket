"""
    Support Ticket Student URL Configuration
"""
from django.urls import path

from ..views.highschool_admins import (
    tickets as requests, details, add_new
)

app_name = 'hs_admin_support_ticket'
urlpatterns = [
    path('', requests, name='requests'),
    path('add_new', add_new, name='add_new'),
    path('<uuid:record_id>', details, name='details'),
]
