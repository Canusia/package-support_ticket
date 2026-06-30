"""
Regression tests: TicketAttachment filenames must appear in all four portal
detail-page templates.

Each test creates a ticket with a named attachment and asserts that the
filename shows up in the rendered HTML — confirming that the attachment loop
in the template is working and not the deleted record.media field.

Also covers three CE-detail bugs fixed in the feature/support-requests branch:
  #1 UnboundLocalError (500) on invalid add-note POST
  #1 UnboundLocalError (500) on invalid assignment POST
  #2 CE notes must save with note_type='Public' so submitters can see them
  #6 File attachments on CE notes must be persisted
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from support_ticket.models.ticket import Ticket, TicketNote, TicketType
from support_ticket.services import create_ticket_with_files

User = get_user_model()


def _login(user):
    """force_login via Django test Client, neutralising the login-history signal."""
    from django.contrib.auth.signals import user_logged_in
    from django_login_history.models import post_login
    user_logged_in.disconnect(post_login)
    try:
        c = Client()
        c.force_login(user)
    finally:
        user_logged_in.connect(post_login)
    return c


def _dummy_url(name):
    """Return a predictable URL so the template renders without hitting S3."""
    return f'/media/{name}'


def _no_rename(name, max_length=None):
    """Stub storage.get_available_name so the stored filename keeps the original name (no suffix)."""
    return name


class StudentDetailAttachmentRenderTest(TestCase):
    """Student portal: attachment filename appears in the detail page."""

    def setUp(self):
        self.u = User.objects.create(email='stu_det@example.com')
        self.u.groups.add(Group.objects.get_or_create(name='student')[0])
        self.tt = TicketType.objects.create(name='STDet', applies_to='Students')

    @patch('cis.storage_backend.PrivateMediaStorage.get_available_name', side_effect=_no_rename)
    @patch('cis.storage_backend.PrivateMediaStorage.url', side_effect=_dummy_url)
    def test_attachment_filename_in_response(self, _mock_url, _mock_rename):
        ticket = create_ticket_with_files(
            self.u, self.tt, 'need help',
            [SimpleUploadedFile('proof.pdf', b'x')])
        c = _login(self.u)
        resp = c.get(reverse('student_support_ticket:details',
                             args=[ticket.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'proof.pdf')


class InstructorDetailAttachmentRenderTest(TestCase):
    """Instructor portal: attachment filename appears in the detail page."""

    def setUp(self):
        self.u = User.objects.create(
            email='instr_det@example.com', username='instr_det@example.com')
        self.u.groups.add(Group.objects.get_or_create(name='instructor')[0])
        self.tt = TicketType.objects.create(name='IDet', applies_to='Instructors')

    @patch('cis.storage_backend.PrivateMediaStorage.get_available_name', side_effect=_no_rename)
    @patch('cis.storage_backend.PrivateMediaStorage.url', side_effect=_dummy_url)
    def test_attachment_filename_in_response(self, _mock_url, _mock_rename):
        ticket = create_ticket_with_files(
            self.u, self.tt, 'need help',
            [SimpleUploadedFile('invoice.pdf', b'x')])
        c = _login(self.u)
        resp = c.get(reverse('instructor_support_ticket:details',
                             args=[ticket.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'invoice.pdf')


class CEDetailAttachmentRenderTest(TestCase):
    """CE (staff) portal: attachment filename appears in the detail page."""

    def setUp(self):
        self.ce_user = User.objects.create(
            email='ce_det@example.com', username='ce_det@example.com')
        self.ce_user.groups.add(Group.objects.get_or_create(name='ce')[0])

        self.student = User.objects.create(
            email='stu_ce_det@example.com', username='stu_ce_det@example.com')
        self.tt = TicketType.objects.create(name='CEDet', applies_to='Students')

    @patch('cis.storage_backend.PrivateMediaStorage.get_available_name', side_effect=_no_rename)
    @patch('cis.storage_backend.PrivateMediaStorage.url', side_effect=_dummy_url)
    def test_attachment_filename_in_response(self, _mock_url, _mock_rename):
        ticket = create_ticket_with_files(
            self.student, self.tt, 'issue',
            [SimpleUploadedFile('report.pdf', b'x')])
        c = _login(self.ce_user)
        # CE detail URL: support_ticket:request with record_id kwarg
        resp = c.get(reverse('support_ticket:request', args=[ticket.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'report.pdf')


# ---------------------------------------------------------------------------
# Bug-fix regression tests (feature/support-requests)
# ---------------------------------------------------------------------------

class CEDetailBugFixBase(TestCase):
    """Shared setUp for the three CE-detail bug-fix tests."""

    def setUp(self):
        self.ce_user = User.objects.create(
            email='ce_fix@example.com', username='ce_fix@example.com')
        self.ce_user.groups.add(Group.objects.get_or_create(name='ce')[0])

        self.student = User.objects.create(
            email='stu_fix@example.com', username='stu_fix@example.com')
        self.student.groups.add(Group.objects.get_or_create(name='student')[0])

        self.tt = TicketType.objects.create(name='FixType', applies_to='Students')
        self.ticket = create_ticket_with_files(
            self.student, self.tt, 'help me', [])
        self.url = reverse('support_ticket:request', args=[self.ticket.id])
        self.client = _login(self.ce_user)


class CEDetailInvalidNotePostNo500Test(CEDetailBugFixBase):
    """Bug #1: invalid add-note POST must return 200 (form re-render), not 500."""

    def test_ce_detail_invalid_note_post_no_500(self):
        # POST add_note with empty 'note' — should fail validation, not 500
        resp = self.client.post(self.url, {
            'add_note': 'Add Note',
            'note': '',          # empty → invalid
        })
        self.assertEqual(resp.status_code, 200,
                         "Expected 200 re-render for invalid note POST, got 500")
        # No note should have been created
        self.assertEqual(TicketNote.objects.filter(support_ticket=self.ticket).count(), 0)


class CEDetailInvalidAssignmentPostNo500Test(CEDetailBugFixBase):
    """Bug #1: invalid assignment POST must return 200, not 500."""

    def test_ce_detail_invalid_assignment_post_no_500(self):
        # POST without add_note, with an obviously bad status value that passes
        # the form but we can also test with missing assigned_to.
        resp = self.client.post(self.url, {
            # no add_note key → assignment branch
            # omit assigned_to → ModelChoiceField invalid
            'status': 'Submitted',
        })
        self.assertEqual(resp.status_code, 200,
                         "Expected 200 re-render for invalid assignment POST, got 500")


class CENoteSavedPublicTest(CEDetailBugFixBase):
    """Bug #2: CE note must be saved with note_type='Public' so submitters can see it."""

    def test_ce_note_saved_public_and_visible_to_submitter(self):
        resp = self.client.post(self.url, {
            'add_note': 'Add Note',
            'note': 'Here is my reply',
            'id': '-1',
            'model': 'ticketnote',
            'add_to': str(self.ticket.id),
            'ajax': '0',
        })
        # Successful note POST → redirect
        self.assertEqual(resp.status_code, 302)

        note = TicketNote.objects.get(support_ticket=self.ticket)
        self.assertEqual(note.note_type, 'Public',
                         "CE note must be saved with note_type='Public'")

        # Submitter's student portal detail view filters note_type='Public';
        # the note text must appear in that view.
        student_client = _login(self.student)
        student_url = reverse('student_support_ticket:details', args=[self.ticket.id])
        student_resp = student_client.get(student_url)
        self.assertEqual(student_resp.status_code, 200)
        self.assertContains(student_resp, 'Here is my reply')


class CEDetailNoteWithFileCreatesAttachmentTest(CEDetailBugFixBase):
    """Bug #6: files attached to a CE note must be persisted as TicketAttachment rows."""

    @patch('cis.storage_backend.PrivateMediaStorage.get_available_name', side_effect=_no_rename)
    @patch('cis.storage_backend.PrivateMediaStorage.url', side_effect=_dummy_url)
    def test_ce_note_with_file_creates_attachment(self, _mock_url, _mock_rename):
        upload = SimpleUploadedFile('note_attach.pdf', b'pdf-content')
        resp = self.client.post(self.url, {
            'add_note': 'Add Note',
            'note': 'See attached',
            'id': '-1',
            'model': 'ticketnote',
            'add_to': str(self.ticket.id),
            'ajax': '0',
            'files': [upload],
        })
        self.assertEqual(resp.status_code, 302)

        note = TicketNote.objects.get(support_ticket=self.ticket)
        self.assertEqual(note.attachments.count(), 1,
                         "Expected 1 TicketAttachment on the CE note")
