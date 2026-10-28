from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from user_management.management.commands.sync_users import Command


def make_diff(project, project_id, group):
    return {
        "project": project,
        "project_id": project_id,
        "group": group,
        "missing_from_external": [],
        "missing_from_coldfront": ["jdoe"],
    }


@override_settings(MANAGE_GROUPS_AT_PROJECT_LEVEL=True)
class SyncToColdfrontFailureTests(TestCase):
    """A project that fails to sync is reported, and the sync carries on with the others."""

    def run_sync(self, differences, sync_side_effect):
        out, err = StringIO(), StringIO()
        with (
            patch.object(Command, "collate_project_user_data", return_value=[]),
            patch.object(Command, "collate_external_user_data", return_value={}),
            patch.object(Command, "compare_coldfront_to_external", return_value=differences),
            patch.object(Command, "sync_to_coldfront", side_effect=sync_side_effect) as sync_to_coldfront,
        ):
            call_command("sync_users", stdout=out, stderr=err)
        return out.getvalue(), err.getvalue(), sync_to_coldfront

    def test_a_failing_project_does_not_stop_the_others(self):
        differences = [make_diff("Ocean", 1, "ocean-grp"), make_diff("Glacier", 2, "glacier-grp")]

        out, err, sync_to_coldfront = self.run_sync(differences, [RuntimeError("LDAP timed out"), None])

        self.assertEqual(sync_to_coldfront.call_count, 2)
        self.assertIn("Sync complete.", out)
        self.assertIn(
            "Failed syncing project Ocean (ID: 1), group ocean-grp, to ColdFront: RuntimeError: LDAP timed out", err
        )
        self.assertNotIn("Glacier", err)
