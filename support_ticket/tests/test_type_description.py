"""Request-type description: CE writes it on the type; requesters see the
picked type's text on the add-new page (with any document link in it)."""
import json
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from cis.models.settings import Setting
from ..forms.types import SupportTicketForm, TicketTypeForm
from ..models.ticket import TicketType
from ..settings.support_ticket_settings import support_ticket_settings as STS
from .test_submission import _login

User = get_user_model()
LINK = '<p>Download <a href="/documents/file/11111111-1111-1111-1111-111111111111/">the form</a>.</p>'


def _descriptions(response):
    match = re.search(
        r'<script id="ticket_type_descriptions" type="application/json">(.*?)</script>',
        response.content.decode(), re.S)
    return json.loads(match.group(1)) if match else None


class TypeDescriptionFormTests(TestCase):
    def test_type_form_saves_description(self):
        form = TicketTypeForm(data={
            'name': 'Name change', 'applies_to': TicketType.SCHOOL_ADMINS,
            'description': LINK})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().description, LINK)

    def test_description_is_optional(self):
        form = TicketTypeForm(data={'name': 'Other', 'applies_to': TicketType.STUDENTS})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().description, '')

    def test_request_form_lists_only_its_roles_described_types(self):
        hs = TicketType.objects.create(
            name='Name change', applies_to=TicketType.SCHOOL_ADMINS, description=LINK)
        TicketType.objects.create(
            name='Blank', applies_to=TicketType.SCHOOL_ADMINS)
        TicketType.objects.create(
            name='Student only', applies_to=TicketType.STUDENTS, description='secret')
        self.assertEqual(
            SupportTicketForm('highschool_admin').type_descriptions(),
            {str(hs.pk): LINK})


class TypeDescriptionPageTests(TestCase):
    def _page(self, role, url_name, applies_to):
        Setting.objects.update_or_create(
            key=STS.key, defaults={'value': {'who_can_start': [role]}})
        user = User.objects.create(email=f'{role}_td@example.com',
                                   username=f'{role}_td@example.com')
        user.groups.add(Group.objects.get_or_create(name=role)[0])
        mine = TicketType.objects.create(
            name='Mine', applies_to=applies_to, description=LINK)
        other = [a for a, _ in TicketType.APPLIES_TO if a != applies_to][0]
        TicketType.objects.create(name='Not mine', applies_to=other, description='nope')
        response = _login(user).get(reverse(url_name))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_descriptions(response), {str(mine.pk): LINK})
        self.assertContains(response, 'id="ticket_type_description"')

    def test_student_page(self):
        self._page('student', 'student_support_ticket:add_new', TicketType.STUDENTS)

    def test_instructor_page(self):
        self._page('instructor', 'instructor_support_ticket:add_new', TicketType.INSTRUCTORS)

    def test_hs_admin_page(self):
        self._page('highschool_admin', 'hs_admin_support_ticket:add_new',
                   TicketType.SCHOOL_ADMINS)

    def test_ce_type_page_loads_editor_media(self):
        ce = User.objects.create(email='ce_td@example.com', username='ce_td@example.com')
        ce.groups.add(Group.objects.get_or_create(name='ce')[0])
        tt = TicketType.objects.create(name='Edit me', applies_to=TicketType.STUDENTS)
        response = _login(ce).get(reverse('support_ticket:type', args=[tt.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="description"')
