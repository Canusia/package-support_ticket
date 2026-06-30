"""
    Support Ticket Student URL Configuration
"""
from django.urls import path

from ..views.students import (
    tickets as requests, details, add_new
)

app_name = 'student_support_ticket'
urlpatterns = [
    path('', requests, name='requests'),
    path('add_new', add_new, name='add_new'),
    path('<uuid:record_id>', details, name='details'),
]
