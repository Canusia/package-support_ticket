import time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from ..constants import (
    ROLE_TO_APPLIES_TO, APPLIES_TO_TO_ROLE, DEFAULT_STATUSES,
)
from ..models.ticket import Ticket, TicketNote, TicketType
from ..models.attachment import TicketAttachment

User = get_user_model()


class ConstantsTests(TestCase):
    def test_role_to_applies_to_covers_three_roles(self):
        self.assertEqual(ROLE_TO_APPLIES_TO['student'], 'Students')
        self.assertEqual(ROLE_TO_APPLIES_TO['instructor'], 'Instructors')
        self.assertEqual(
            ROLE_TO_APPLIES_TO['highschool_admin'], 'High School Administrators')

    def test_inverse_map_round_trips(self):
        for role, applies in ROLE_TO_APPLIES_TO.items():
            self.assertEqual(APPLIES_TO_TO_ROLE[applies], role)

    def test_default_statuses(self):
        self.assertEqual(DEFAULT_STATUSES[0], 'Submitted')
        self.assertIn('Closed', DEFAULT_STATUSES)


class TicketTypeTests(TestCase):
    def test_instructors_is_a_valid_applies_to(self):
        self.assertIn(('Instructors', 'Instructors'), TicketType.APPLIES_TO)

    def test_notify_recipient_emails_merges_users_and_emails(self):
        u = User.objects.create(email='ce1@example.com')
        u.set_unusable_password()
        u.save()
        t = TicketType.objects.create(
            name='Tech', applies_to='Students',
            notify_emails='extra@example.com, second@example.com')
        t.notify_users.add(u)
        emails = t.notify_recipient_emails()
        self.assertIn('ce1@example.com', emails)
        self.assertIn('extra@example.com', emails)
        self.assertIn('second@example.com', emails)

    def test_requires_attachment_defaults_false(self):
        t = TicketType.objects.create(name='Q', applies_to='Students')
        self.assertFalse(t.requires_attachment)


class TicketAttachmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(email='s@example.com')
        self.tt = TicketType.objects.create(name='Tech', applies_to='Students')
        self.ticket = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.user, message='help')

    def test_attachment_requires_exactly_one_parent(self):
        a = TicketAttachment(media=SimpleUploadedFile('a.txt', b'x'))
        with self.assertRaises(ValidationError):
            a.clean()  # neither ticket nor note

    def test_attachment_rejects_two_parents(self):
        note = TicketNote.objects.create(
            support_ticket=self.ticket, note='n', createdby=self.user)
        a = TicketAttachment(
            ticket=self.ticket, note=note, media=SimpleUploadedFile('a.txt', b'x'))
        with self.assertRaises(ValidationError):
            a.clean()

    def test_ticket_attachments_related_name(self):
        TicketAttachment.objects.create(
            ticket=self.ticket, media=SimpleUploadedFile('a.txt', b'x'))
        self.assertEqual(self.ticket.attachments.count(), 1)


class MediaFieldRemovedTests(TestCase):
    def test_ticket_has_no_media_field(self):
        from ..models.ticket import Ticket
        field_names = {f.name for f in Ticket._meta.get_fields()}
        self.assertNotIn('media', field_names)

    def test_note_has_no_media_field(self):
        from ..models.ticket import TicketNote
        field_names = {f.name for f in TicketNote._meta.get_fields()}
        self.assertNotIn('media', field_names)


class TicketDateFieldTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(email='d@example.com')
        self.tt = TicketType.objects.create(name='T', applies_to='Students')

    def test_submitted_on_is_stable_last_updated_changes(self):
        t = Ticket.objects.create(
            ticket_type=self.tt, submitted_by=self.user, message='hi')
        created = t.submitted_on
        first_updated = t.last_updated_on
        time.sleep(0.01)
        t.message = 'changed'
        t.save()
        t.refresh_from_db()
        self.assertEqual(t.submitted_on, created)        # created time stable
        self.assertGreater(t.last_updated_on, first_updated)  # modified advances
