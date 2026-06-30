from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from cis.models.settings import Setting
from support_ticket.forms.fields import MultipleFileField
from support_ticket.forms.types import SupportTicketForm, SupportTicketAssignmentForm
from support_ticket.models.ticket import Ticket, TicketNote, TicketType
from support_ticket.services import create_ticket_with_files, add_note_with_files
from support_ticket.settings.support_ticket_settings import support_ticket_settings as STS

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


class _F(forms.Form):
    files = MultipleFileField(required=False)


class MultipleFileFieldTests(TestCase):
    def test_clean_returns_list_for_multiple(self):
        f = _F(files={'files': [
            SimpleUploadedFile('a.txt', b'a'), SimpleUploadedFile('b.txt', b'b')]})
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(len(f.cleaned_data['files']), 2)

    def test_empty_ok_when_optional(self):
        f = _F(data={}, files={})
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.cleaned_data['files'], [])

    def test_clean_wraps_single_file_in_list(self):
        f = _F(files={'files': SimpleUploadedFile('one.txt', b'x')})
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(len(f.cleaned_data['files']), 1)


class CreateTicketServiceTests(TestCase):
    def test_creates_ticket_and_attachments(self):
        u = User.objects.create(email='s@example.com', username='user_s')
        tt = TicketType.objects.create(name='Tech', applies_to='Students')
        t = create_ticket_with_files(
            u, tt, 'help', [SimpleUploadedFile('a.txt', b'a'),
                            SimpleUploadedFile('b.txt', b'b')])
        self.assertIsInstance(t, Ticket)
        self.assertEqual(t.submitted_by, u)
        self.assertEqual(t.attachments.count(), 2)
        self.assertTrue(all(a.uploaded_by_id == u.id for a in t.attachments.all()))


class AddNoteServiceTests(TestCase):
    def test_creates_note_and_attachments(self):
        u = User.objects.create(email='n@example.com', username='user_n')
        tt = TicketType.objects.create(name='Other', applies_to='Students')
        ticket = Ticket.objects.create(ticket_type=tt, submitted_by=u, message='hi')
        note = add_note_with_files(
            u, ticket, 'follow-up', 'Public', [SimpleUploadedFile('c.txt', b'c')])
        self.assertEqual(note.attachments.count(), 1)
        self.assertEqual(note.attachments.first().uploaded_by_id, u.id)
        self.assertEqual(note.note_type, 'Public')

    def test_no_files_creates_no_attachments(self):
        u = User.objects.create(email='n2@example.com', username='user_n2')
        tt = TicketType.objects.create(name='Other2', applies_to='Students')
        ticket = Ticket.objects.create(ticket_type=tt, submitted_by=u, message='hi')
        note = add_note_with_files(u, ticket, 'text', 'Internal', None)
        self.assertEqual(note.attachments.count(), 0)


class AssignmentFormStatusChoicesTests(TestCase):
    def test_status_choices_from_settings(self):
        Setting.objects.update_or_create(
            key=STS.key,
            defaults={'value': {'statuses': 'New\nDone'}},
        )
        form = SupportTicketAssignmentForm()
        labels = [c[0] for c in form.fields['status'].choices]
        self.assertEqual(labels, ['New', 'Done'])


class SupportTicketFormTests(TestCase):
    def setUp(self):
        self.student_type = TicketType.objects.create(name='S', applies_to='Students')
        self.instr_type = TicketType.objects.create(name='I', applies_to='Instructors')
        self.hs_type = TicketType.objects.create(
            name='H', applies_to='High School Administrators')
        self.req_type = TicketType.objects.create(
            name='NeedsDoc', applies_to='Students', requires_attachment=True)

    def test_ticket_type_queryset_filtered_by_role(self):
        form = SupportTicketForm('student')
        labels = set(form.fields['ticket_type'].queryset.values_list('name', flat=True))
        self.assertEqual(labels, {'S', 'NeedsDoc'})   # no Instructors-only type

    def test_requires_attachment_rejected_without_file(self):
        form = SupportTicketForm(
            'student',
            data={'ticket_type': str(self.req_type.id), 'message': 'hi'}, files={})
        self.assertFalse(form.is_valid())
        self.assertIn('files', form.errors)

    def test_requires_attachment_accepted_with_file(self):
        form = SupportTicketForm(
            'student',
            data={'ticket_type': str(self.req_type.id), 'message': 'hi'},
            files={'files': [SimpleUploadedFile('a.txt', b'a')]})
        self.assertTrue(form.is_valid(), form.errors)

    def test_ticket_type_queryset_instructor_only(self):
        """Instructor role shows only Instructors applies_to types."""
        form = SupportTicketForm('instructor')
        labels = set(form.fields['ticket_type'].queryset.values_list('name', flat=True))
        self.assertIn('I', labels)
        self.assertNotIn('S', labels)
        self.assertNotIn('H', labels)

    def test_ticket_type_queryset_highschool_admin_only(self):
        """highschool_admin role shows only High School Administrators applies_to types."""
        form = SupportTicketForm('highschool_admin')
        labels = set(form.fields['ticket_type'].queryset.values_list('name', flat=True))
        self.assertIn('H', labels)
        self.assertNotIn('S', labels)
        self.assertNotIn('I', labels)


class StudentCreateViewTests(TestCase):
    def setUp(self):
        self.u = User.objects.create(email='stu@example.com')
        self.u.groups.add(Group.objects.get_or_create(name='student')[0])
        self.c = _login(self.u)
        self.tt = TicketType.objects.create(name='Tech', applies_to='Students')

    def test_blocked_when_role_cannot_start(self):
        Setting.objects.update_or_create(
            key=STS.key, defaults={'value': {'who_can_start': ['instructor']}})
        resp = self.c.post(reverse('student_support_ticket:add_new'), {
            'ticket_type': str(self.tt.id), 'message': 'hi'})
        self.assertIn(resp.status_code, (302, 403))
        self.assertEqual(Ticket.objects.count(), 0)

    def test_creates_ticket_with_multiple_files(self):
        Setting.objects.update_or_create(
            key=STS.key, defaults={'value': {'who_can_start': ['student']}})
        resp = self.c.post(reverse('student_support_ticket:add_new'), {
            'ticket_type': str(self.tt.id), 'message': 'hi',
            'files': [SimpleUploadedFile('a.txt', b'a'), SimpleUploadedFile('b.txt', b'b')],
        })
        self.assertEqual(resp.status_code, 302)
        t = Ticket.objects.get()
        self.assertEqual(t.attachments.count(), 2)
        self.assertEqual(t.submitted_by, self.u)


class InstructorCreateViewTests(TestCase):
    def setUp(self):
        self.u = User.objects.create(
            email='instr_cv@example.com', username='instr_cv@example.com')
        self.u.groups.add(Group.objects.get_or_create(name='instructor')[0])
        self.c = _login(self.u)
        self.tt = TicketType.objects.create(name='InstrTech', applies_to='Instructors')

    def test_blocked_when_role_cannot_start(self):
        Setting.objects.update_or_create(
            key=STS.key, defaults={'value': {'who_can_start': ['student']}})
        resp = self.c.post(reverse('instructor_support_ticket:add_new'), {
            'ticket_type': str(self.tt.id), 'message': 'hi'})
        self.assertIn(resp.status_code, (302, 403))
        self.assertEqual(Ticket.objects.count(), 0)

    def test_creates_ticket(self):
        Setting.objects.update_or_create(
            key=STS.key, defaults={'value': {'who_can_start': ['instructor']}})
        resp = self.c.post(reverse('instructor_support_ticket:add_new'), {
            'ticket_type': str(self.tt.id), 'message': 'hi',
        })
        self.assertEqual(resp.status_code, 302)
        t = Ticket.objects.get()
        self.assertEqual(t.submitted_by, self.u)


class HSAdminCreateViewTests(TestCase):
    def setUp(self):
        self.u = User.objects.create(
            email='hsadmin_cv@example.com', username='hsadmin_cv@example.com')
        self.u.groups.add(Group.objects.get_or_create(name='highschool_admin')[0])
        self.c = _login(self.u)
        self.tt = TicketType.objects.create(
            name='HSTech', applies_to='High School Administrators')

    def test_blocked_when_role_cannot_start(self):
        Setting.objects.update_or_create(
            key=STS.key, defaults={'value': {'who_can_start': ['student']}})
        resp = self.c.post(reverse('hs_admin_support_ticket:add_new'), {
            'ticket_type': str(self.tt.id), 'message': 'hi'})
        self.assertIn(resp.status_code, (302, 403))
        self.assertEqual(Ticket.objects.count(), 0)

    def test_creates_ticket(self):
        Setting.objects.update_or_create(
            key=STS.key, defaults={'value': {'who_can_start': ['highschool_admin']}})
        resp = self.c.post(reverse('hs_admin_support_ticket:add_new'), {
            'ticket_type': str(self.tt.id), 'message': 'hi',
        })
        self.assertEqual(resp.status_code, 302)
        t = Ticket.objects.get()
        self.assertEqual(t.submitted_by, self.u)


class NewSupportTicketFormChoicesTests(TestCase):
    def test_send_to_excludes_instructors(self):
        from support_ticket.forms.types import NewSupportTicketForm
        values = [c[0] for c in NewSupportTicketForm().fields['send_to'].choices]
        self.assertIn('Students', values)
        self.assertIn('High School Administrators', values)
        self.assertNotIn('Instructors', values)

    def test_school_admins_branch_removes_student_field(self):
        """Bug #5: send_to='High School Administrators' must remove 'student' and keep 'administrator'."""
        from support_ticket.forms.types import NewSupportTicketForm
        form = NewSupportTicketForm(initial={'send_to': 'High School Administrators'})
        self.assertIn('administrator', form.fields)
        self.assertNotIn('student', form.fields)

    def test_students_branch_removes_administrator_field(self):
        """Bug #5 (symmetric): send_to='Students' must remove 'administrator' and keep 'student'."""
        from support_ticket.forms.types import NewSupportTicketForm
        form = NewSupportTicketForm(initial={'send_to': 'Students'})
        self.assertIn('student', form.fields)
        self.assertNotIn('administrator', form.fields)


class NewButtonGatingTests(TestCase):
    def test_button_hidden_when_role_disabled(self):
        u = User.objects.create(email='stu2@example.com')
        u.groups.add(Group.objects.get_or_create(name='student')[0])
        Setting.objects.update_or_create(
            key=STS.key, defaults={'value': {'who_can_start': []}})
        c = _login(u)
        resp = c.get(reverse('student_support_ticket:requests'))
        self.assertFalse(resp.context['can_start'])
