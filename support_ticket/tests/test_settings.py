from importlib import import_module

from django.apps import apps as django_apps
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from cis.models.settings import Setting
from ..settings.support_ticket_settings import support_ticket_settings as STS

# Built from this package's own path so it resolves both in-tree
# (support_ticket.support_ticket) and pip-installed (support_ticket) (#3).
_pkg = __package__.rsplit('.tests', 1)[0]
_migration_0007 = import_module(f'{_pkg}.migrations.0007_migrate_legacy_settings_key')
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


def _post_data(**overrides):
    """A valid settings POST (static fields only); overrides add per-status keys."""
    data = {
        'is_active': 'Yes', 'who_can_start': ['student'], 'default_to': '',
        'statuses': 'Submitted\nPending\nClosed',
        'submission_subject': '', 'submission_email': '',
        'assignment_subject': '', 'assignment_email': '',
        'note_subject': '', 'note_email': '',
    }
    data.update(overrides)
    return data


class PerStatusFieldsFollowSubmittedStatusesTests(TestCase):
    """#4: per-status fields come from the submitted status list when the form is bound."""

    def setUp(self):
        Setting.objects.update_or_create(key=STS.key, defaults={'value': {
            'statuses': 'Submitted\nPending\nClosed',
            'status_closed_subject': 'Closed subject',
        }})

    def _save(self, data):
        form = STS(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        form.run_record()
        return Setting.objects.get(key=STS.key).value

    def test_new_status_templates_saved_in_one_save(self):
        value = self._save(_post_data(
            statuses='New\nWorking\nDone',
            status_working_notify='on',
            status_working_subject='Now working',
            status_working_email='We are on it, {{first_name}}',
        ))
        self.assertEqual(value['statuses'], 'New\nWorking\nDone')
        self.assertEqual(value['status_working_subject'], 'Now working')
        self.assertTrue(value['status_working_notify'])
        self.assertEqual(STS.status_template('Working')['subject'], 'Now working')

    def test_removed_status_drops_its_keys(self):
        value = self._save(_post_data(statuses='Submitted\nPending'))
        self.assertNotIn('status_closed_subject', value)
        self.assertNotIn('status_closed_email', value)

    def test_blank_submitted_statuses_falls_back_to_saved_list(self):
        form = STS(data=_post_data(statuses=''))
        self.assertIn('status_closed_subject', form.fields)

    def test_unbound_form_uses_saved_statuses(self):
        form = STS()
        self.assertIn('status_closed_subject', form.fields)
        self.assertEqual(form.fields['status_closed_subject'].initial, 'Closed subject')
        self.assertNotIn('status_working_subject', form.fields)
