"""Shared constants for the support_ticket app."""

ROLE_TO_APPLIES_TO = {
    'student': 'Students',
    'highschool_admin': 'High School Administrators',
    'instructor': 'Instructors',
}

APPLIES_TO_TO_ROLE = {v: k for k, v in ROLE_TO_APPLIES_TO.items()}

DEFAULT_STATUSES = ['Submitted', 'Pending', 'Closed']
