"""Portal support pages follow the renamed menu item and show saved page text (#8).

RVC renamed the HS admin "Support Requests" menu item to "Bulk Form Upload";
the page kept the hard-coded heading and never showed the support_blurb staff
saved for it.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from .. import portal_text
from ..models.ticket import TicketType
from ..services import create_ticket_with_files
from ..settings.support_ticket_settings import support_ticket_settings as STS

User = get_user_model()

BLURB = 'Please upload class files here. Do NOT upload rosters.'

# (role, group, url namespace, applies_to, portal setting class path)
PORTALS = [
    ('highschool_admin', 'highschool_admin', 'hs_admin_support_ticket',
     'High School Administrators',
     'cis.settings.highschool_admin_portal.highschool_admin_portal'),
    ('instructor', 'instructor', 'instructor_support_ticket', 'Instructors',
     'cis.settings.instructor_portal.instructor_portal'),
    ('student', 'student', 'student_support_ticket', 'Students',
     'cis.settings.student_portal.student_portal'),
]


def _login(user):
    from django.contrib.auth.signals import user_logged_in
    from django_login_history.models import post_login
    user_logged_in.disconnect(post_login)
    try:
        c = Client()
        c.force_login(user)
    finally:
        user_logged_in.connect(post_login)
    return c


def _menu(label):
    return [{'name': 'home', 'label': 'Home'},
            {'name': 'support', 'label': label}]


class PageHeadingTests(TestCase):

    def test_renamed_item_gives_its_label(self):
        with patch('cis.menu.get_role_menu', return_value=_menu('Bulk Form Upload')):
            self.assertEqual(
                portal_text.page_heading('highschool_admin', 'Support Requests'),
                'Bulk Form Upload')

    def test_stock_label_keeps_default(self):
        with patch('cis.menu.get_role_menu', return_value=_menu('Support Requests')):
            self.assertEqual(
                portal_text.page_heading('student', 'Support Requests'),
                'Support Requests')
            self.assertIsNone(portal_text.renamed_label('student'))

    def test_reads_hidden_items_too(self):
        with patch('cis.menu.get_role_menu', return_value=_menu('X')) as m:
            portal_text.renamed_label('student')
        self.assertEqual(m.call_args.kwargs.get('visible_only'), False)

    def test_item_moved_into_a_group_is_found(self):
        menu = [{'name': 'tools', 'label': 'Tools',
                 'sub_menu': [{'name': 'support', 'label': 'Help Desk'}]}]
        with patch('cis.menu.get_role_menu', return_value=menu):
            self.assertEqual(portal_text.renamed_label('instructor'), 'Help Desk')

    def test_missing_item_blank_label_or_menu_error_keep_default(self):
        for menu in ([{'name': 'home', 'label': 'Home'}], _menu('  ')):
            with patch('cis.menu.get_role_menu', return_value=menu):
                self.assertIsNone(portal_text.renamed_label('instructor'))
        with patch('cis.menu.get_role_menu', side_effect=RuntimeError('boom')):
            self.assertIsNone(portal_text.renamed_label('instructor'))


def _text(role, stored=None, **kw):
    """Patch where this cis reads ``role``'s portal text."""
    try:
        from cis import portal_text as cis_pt
    except ImportError:
        cis_pt = None
    if cis_pt is not None and hasattr(cis_pt, 'role_portal_text'):
        return patch.object(cis_pt, 'role_portal_text', return_value=stored, **kw)
    return patch.object(portal_text, '_stored_text', return_value=stored, **kw)


class PageBlurbTests(TestCase):

    def test_reads_support_blurb_from_each_portal(self):
        for role, *_ in PORTALS:
            with self.subTest(role=role), _text(role, {'support_blurb': BLURB}):
                self.assertEqual(portal_text.page_blurb(role), BLURB)

    def test_blank_or_placeholder_gives_empty(self):
        for stored in ({}, {'support_blurb': '   '},
                       {'support_blurb': 'Change me'},
                       {'support_blurb': 'Change this in Settings -> Student -> Portal Language'}):
            with _text('highschool_admin', stored):
                self.assertEqual(portal_text.page_blurb('highschool_admin'), '')

    def test_unknown_role_gives_empty(self):
        self.assertEqual(portal_text.page_blurb('ce'), '')


class OlderCisFallbackTests(TestCase):
    """On a cis without cis.portal_text.page_heading/page_blurb."""

    def _no_cis_helpers(self, portal_text_fn=None):
        return patch.object(portal_text, '_cis_helper',
                            side_effect=lambda name: portal_text_fn if name == 'portal_text' else None)

    def test_heading_from_the_menu(self):
        with self._no_cis_helpers(), \
                patch('cis.menu.get_role_menu', return_value=_menu('Bulk Form Upload')):
            self.assertEqual(portal_text.renamed_label('highschool_admin'), 'Bulk Form Upload')
        with self._no_cis_helpers(), \
                patch('cis.menu.get_role_menu', return_value=_menu('Support Requests')):
            self.assertIsNone(portal_text.renamed_label('student'))

    def test_instructor_text_follows_the_owning_package(self):
        """cis#82: instructor text lives in package-instructor_portal when installed."""
        owned = lambda name: {'support_blurb': f'from {name}'}
        with self._no_cis_helpers(owned):
            self.assertEqual(portal_text.page_blurb('instructor'), 'from instructor_portal')

    def test_hs_admin_text_from_cis_setting(self):
        with self._no_cis_helpers(), \
                patch(f'{PORTALS[0][4]}.from_db', return_value={'support_blurb': BLURB}):
            self.assertEqual(portal_text.page_blurb('highschool_admin'), BLURB)

    def test_bad_or_unreadable_text_gives_empty(self):
        for stored in (None, ['x'], 'x', {'support_blurb': 'Change me'}):
            with self._no_cis_helpers(), \
                    patch.object(portal_text, '_stored_text', return_value=stored):
                self.assertEqual(portal_text.page_blurb('student'), '')
        with self._no_cis_helpers(), \
                patch.object(portal_text, '_stored_text', side_effect=RuntimeError('boom')):
            self.assertEqual(portal_text.page_blurb('student'), '')


class PortalPagesTests(TestCase):
    """Each portal's list, add and detail pages use the label and the blurb."""

    def _user(self, role, group):
        u = User.objects.create(email=f'{role}_pt@example.com',
                                username=f'{role}_pt@example.com')
        u.groups.add(Group.objects.get_or_create(name=group)[0])
        return u

    def _get(self, client, ns, page, *args):
        return client.get(reverse(f'{ns}:{page}', args=args))

    def test_renamed_menu_and_blurb(self):
        for role, group, ns, applies_to, setting in PORTALS:
            with self.subTest(role=role):
                user = self._user(role, group)
                tt = TicketType.objects.create(name=f'T-{role}', applies_to=applies_to)
                ticket = create_ticket_with_files(user, tt, 'hello', [])
                c = _login(user)
                with patch('cis.menu.get_role_menu',
                           return_value=_menu('Bulk Form Upload')), \
                        _text(role, {'support_blurb': BLURB}), \
                        patch.object(STS, 'can_start', return_value=True):
                    index = self._get(c, ns, 'requests')
                    add = self._get(c, ns, 'add_new')
                    detail = self._get(c, ns, 'details', ticket.id)
                self.assertEqual(index.status_code, 200)
                self.assertContains(index, 'Bulk Form Upload&nbsp;')
                self.assertNotContains(index, 'Support Requests&nbsp;')
                self.assertContains(index, BLURB)
                self.assertContains(add, 'Bulk Form Upload — New')
                # HS admin detail is scoped to the admin's schools; this user has none.
                if role != 'highschool_admin':
                    self.assertContains(detail, '<title>Bulk Form Upload')

    def test_stock_menu_no_blurb_keeps_todays_pages(self):
        for role, group, ns, applies_to, setting in PORTALS:
            with self.subTest(role=role):
                user = self._user(role, group)
                c = _login(user)
                with patch('cis.menu.get_role_menu',
                           return_value=_menu('Support Requests')), \
                        _text(role, {}):
                    index = self._get(c, ns, 'requests')
                self.assertEqual(index.status_code, 200)
                self.assertContains(index, 'Support Requests&nbsp;')
                self.assertNotContains(index, 'support-page-text')
