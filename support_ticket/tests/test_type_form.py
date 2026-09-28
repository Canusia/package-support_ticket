"""The CE add/edit request-type form exposes every setting on TicketType.

requires_attachment ("require at least one file") and the submission-notify
recipients (notify_users, notify_emails) were on the model but not in
TicketTypeForm.Meta.fields, and the add/edit pages render `form|crispy`, so CE
could not set them anywhere but Django admin.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from ..forms.types import TicketTypeForm
from ..models.ticket import TicketType

User = get_user_model()


class TicketTypeFormFieldsTests(TestCase):
    def setUp(self):
        ce = Group.objects.get_or_create(name='ce')[0]
        self.ce_user = User.objects.create_user(
            username='ce1', email='ce1@example.com', password='x')
        self.ce_user.groups.add(ce)
        self.other = User.objects.create_user(
            username='stu1', email='stu1@example.com', password='x')

    def _data(self, **overrides):
        data = {
            'name': 'Transcript question',
            'applies_to': TicketType.STUDENTS,
            'requires_attachment': 'on',
            'notify_users': [str(self.ce_user.pk)],
            'notify_emails': 'office@example.com, dean@example.com',
        }
        data.update(overrides)
        return data

    def test_form_offers_every_type_setting(self):
        fields = TicketTypeForm().fields
        for name in ('requires_attachment', 'notify_users', 'notify_emails',
                     'assigned_to', 'email_assignee'):
            self.assertIn(name, fields)

    def test_add_saves_requires_attachment_and_notify_recipients(self):
        form = TicketTypeForm(self._data())
        self.assertTrue(form.is_valid(), form.errors)
        record = form.save()
        self.assertTrue(record.requires_attachment)
        self.assertEqual(list(record.notify_users.all()), [self.ce_user])
        self.assertEqual(
            record.notify_recipient_emails(),
            ['ce1@example.com', 'office@example.com', 'dean@example.com'])

    def test_edit_can_turn_requires_attachment_off(self):
        record = TicketType.objects.create(
            name='Old', applies_to=TicketType.STUDENTS, requires_attachment=True)
        data = self._data(name='Old')
        del data['requires_attachment']  # an unchecked box is simply absent
        form = TicketTypeForm(data, instance=record)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        record.refresh_from_db()
        self.assertFalse(record.requires_attachment)

    def test_notify_users_limited_to_ce_staff(self):
        self.assertEqual(
            list(TicketTypeForm().fields['notify_users'].queryset), [self.ce_user])
        form = TicketTypeForm(self._data(notify_users=[str(self.other.pk)]))
        self.assertFalse(form.is_valid())
        self.assertIn('notify_users', form.errors)
