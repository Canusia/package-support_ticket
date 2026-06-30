from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models.ticket import TicketType
from ..reports.ticket_types_export import ticket_types_export

User = get_user_model()


class TicketTypesReportTests(TestCase):
    def test_rows_include_header_and_data(self):
        ce = User.objects.create(email='ce@example.com', first_name='C', last_name='E')
        tt = TicketType.objects.create(
            name='Tech', applies_to='Students', assigned_to=ce,
            notify_emails='w@example.com', requires_attachment=True)
        tt.notify_users.add(ce)
        rows = ticket_types_export().get_rows()
        self.assertEqual(
            rows[0],
            ['Name', 'Applies To', 'Default Assignee', 'Notify Users',
             'Notify Emails', 'Requires Attachment'])
        body = rows[1]
        self.assertEqual(body[0], 'Tech')
        self.assertEqual(body[1], 'Students')
        self.assertEqual(body[5], 'Yes')

    def test_name_is_csv_formula_safe(self):
        TicketType.objects.create(name='=DANGER()', applies_to='Students')
        rows = ticket_types_export().get_rows()
        danger = [r for r in rows[1:] if r[0].endswith('DANGER()')][0]
        self.assertTrue(danger[0].startswith("'"))   # neutralized leading '='
