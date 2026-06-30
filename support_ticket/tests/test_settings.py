from importlib import import_module

from django.apps import apps as django_apps
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from cis.models.settings import Setting
from ..settings.support_ticket_settings import support_ticket_settings as STS

_migration_0007 = import_module(
    'support_ticket.support_ticket.migrations.0007_migrate_legacy_settings_key'
)
_forwards_0007 = _migration_0007.forwards
OLD_KEY = _migration_0007.OLD_KEY
NEW_KEY = _migration_0007.NEW_KEY


class SettingsHelperTests(TestCase):
    def _save(self, value):
        Setting.objects.update_or_create(key=STS.key, defaults={'value': value})

    def test_get_statuses_falls_back_to_defaults(self):
        self.assertEqual(STS.get_statuses(), ['Submitted', 'Pending', 'Closed'])

    def test_get_statuses_parses_textarea(self):
        self._save({'statuses': 'New\nWorking\nDone\n'})
        self.assertEqual(STS.get_statuses(), ['New', 'Working', 'Done'])
        self.assertEqual(STS.get_default_status(), 'New')

    def test_can_start_reads_who_can_start(self):
        self._save({'who_can_start': ['student', 'instructor']})
        self.assertTrue(STS.can_start('student'))
        self.assertTrue(STS.can_start('instructor'))
        self.assertFalse(STS.can_start('highschool_admin'))

    def test_status_template_lookup_by_slug(self):
        self._save({
            'statuses': 'In Review',
            'status_in-review_notify': True,
            'status_in-review_subject': 'Your request is in review',
            'status_in-review_email': 'Hello {{first_name}}',
        })
        tpl = STS.status_template('In Review')
        self.assertTrue(tpl['notify'])
        self.assertEqual(tpl['subject'], 'Your request is in review')

    def test_can_start_permissive_when_unconfigured(self):
        # No who_can_start key (and no DB row) -> permissive default (True for any role)
        self.assertTrue(STS.can_start('student'))
        self.assertTrue(STS.can_start('highschool_admin'))

    def test_can_start_empty_list_blocks_all(self):
        self._save({'who_can_start': []})
        self.assertFalse(STS.can_start('student'))
        self.assertFalse(STS.can_start('highschool_admin'))


class LegacySettingsRouteRemovedTests(TestCase):
    def test_old_settings_route_is_gone(self):
        with self.assertRaises(NoReverseMatch):
            reverse('support_ticket:settings')


class Migration0007SubjectRemapTests(TestCase):
    """Data-fidelity: migration 0007 must remap email_subject -> note_subject."""

    def test_forwards_remaps_email_subject_to_note_subject(self):
        """When old key has email_subject, new key must have note_subject after forwards."""
        Setting.objects.filter(key=OLD_KEY).delete()
        Setting.objects.filter(key=NEW_KEY).delete()
        Setting.objects.create(
            key=OLD_KEY,
            value={'email_subject': 'Custom Subj', 'default_to': 'x@example.com'},
        )
        _forwards_0007(django_apps, None)
        new = Setting.objects.get(key=NEW_KEY)
        self.assertEqual(new.value['note_subject'], 'Custom Subj')

    def test_forwards_preserves_existing_note_subject(self):
        """If new key already has note_subject, do not overwrite it."""
        Setting.objects.filter(key=OLD_KEY).delete()
        Setting.objects.filter(key=NEW_KEY).delete()
        Setting.objects.create(
            key=OLD_KEY,
            value={'email_subject': 'Old Subj'},
        )
        Setting.objects.create(
            key=NEW_KEY,
            value={'note_subject': 'Already Set'},
        )
        _forwards_0007(django_apps, None)
        new = Setting.objects.get(key=NEW_KEY)
        # existing note_subject must NOT be overwritten
        self.assertEqual(new.value['note_subject'], 'Already Set')

    def test_forwards_noop_when_no_old_key(self):
        """forwards is a no-op when the legacy key does not exist."""
        Setting.objects.filter(key=OLD_KEY).delete()
        Setting.objects.filter(key=NEW_KEY).delete()
        _forwards_0007(django_apps, None)
        self.assertFalse(Setting.objects.filter(key=NEW_KEY).exists())
