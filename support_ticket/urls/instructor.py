"""
    Support Ticket Instructor URL Configuration
"""
from django.urls import path

from ..views.instructors import (
    tickets as requests, details, add_new
)

app_name = 'instructor_support_ticket'
urlpatterns = [
    path('', requests, name='requests'),
    path('add/', add_new, name='add_new'),
    path('<uuid:record_id>/', details, name='details'),
]
