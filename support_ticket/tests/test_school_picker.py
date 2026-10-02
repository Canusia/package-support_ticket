"""Campus-scoped school picker on the CE "Add Support Request" form
(cis HighSchoolCampus)."""
import uuid

from django.conf import settings
from django.test import TestCase, override_settings

from cis.campus_context import campus_context
from cis.models.course import Campus
from cis.models.highschool import HighSchool, HighSchoolCampus

from ..forms.types import NewSupportTicketForm


def _sfx():
    return uuid.uuid4().hex[:8]


def _campus():
    return Campus.objects.create(
        name=f'C-{_sfx()}', code=f'{settings.CAMPUS_CODE_PREFIX}_{_sfx()[:6]}')


def _hs(name, campus=None, status='Active'):
    hs = HighSchool.objects.create(name=name, code=_sfx())
    HighSchoolCampus.objects.filter(highschool=hs).delete()
    if campus is not None:
        HighSchoolCampus.objects.create(
            highschool=hs, campus=campus, status=status)
    return hs


class _Base(TestCase):
    def setUp(self):
        self.a, self.b = _campus(), _campus()
        self.mine = _hs('Mine', self.a)
        self.foreign = _hs('Foreign', self.b)
        self.dormant = _hs('Dormant', self.a, 'Inactive')

    def _form(self, send_to='Students', data=None):
        return NewSupportTicketForm(initial={'send_to': send_to}, data=data)


@override_settings(MULTI_CAMPUS=True)
class MultiCampusTests(_Base):
    def test_excludes_other_campus_and_inactive_schools(self):
        for send_to in ('Students', 'High School Administrators'):
            with campus_context(self.a):
                qs = self._form(send_to).fields['highschool'].queryset
                self.assertEqual(list(qs), [self.mine])

    def test_foreign_post_is_rejected(self):
        with campus_context(self.a):
            form = self._form(data={'send_to': 'Students',
                                    'highschool': str(self.foreign.pk)})
            self.assertFalse(form.is_valid())
            self.assertIn('highschool', form.errors)

    def test_own_school_post_passes_field_validation(self):
        with campus_context(self.a):
            form = self._form(data={'send_to': 'Students',
                                    'highschool': str(self.mine.pk)})
            form.is_valid()
            self.assertNotIn('highschool', form.errors)

    def test_a_posted_initial_cannot_smuggle_in_a_foreign_school(self):
        # The view builds the form with initial=request.POST; the school id in
        # it must not widen the options.
        with campus_context(self.a):
            form = NewSupportTicketForm(
                initial={'send_to': 'Students',
                         'highschool': str(self.foreign.pk)},
                data={'send_to': 'Students',
                      'highschool': str(self.foreign.pk)})
            self.assertEqual(
                list(form.fields['highschool'].queryset), [self.mine])
            self.assertFalse(form.is_valid())

    def test_follows_the_request_campus(self):
        with campus_context(self.b):
            qs = self._form().fields['highschool'].queryset
            self.assertEqual(list(qs), [self.foreign])


@override_settings(MULTI_CAMPUS=False)
class SingleCampusTests(_Base):
    def test_options_are_campus_linked_active_schools(self):
        with campus_context(self.a):
            qs = self._form().fields['highschool'].queryset
            self.assertEqual(list(qs), [self.mine])
