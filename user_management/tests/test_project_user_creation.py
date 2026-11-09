"""Only people the directory (LDAP) knows are added to a project from an external group.

A Grouper group can list a username that isn't a real account: one parsed wrongly from a display
name ("Leah(Chanyoung) Lee" gave "Chanyoung"), or someone who has left and has no account any
more. Adding them created a ColdFront user with no name or email and made them an Active member.
"""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from coldfront.core.project.models import ProjectUser
from coldfront.core.test_helpers.factories import (
    PAttributeTypeFactory,
    ProjectAttributeFactory,
    ProjectAttributeTypeFactory,
    ProjectFactory,
    ProjectUserRoleChoiceFactory,
    ProjectUserStatusChoiceFactory,
    UserFactory,
)

from user_management.constants import UNIX_GROUP_ATTRIBUTE_NAME
from user_management.tasks import sync_all_project_users_from_external, sync_project_users_from_external
from user_management.tests.helpers import UserManagementClient
from user_management.utils import UserNotInDirectoryError, create_project_user_from_username
from user_management.views import add_group_members_from_external

DIRECTORY = {
    "jdoe01": {"username": "jdoe01", "first_name": "Jane", "last_name": "Doe", "email": "jane.doe@example.edu"},
    "asmith02": {"username": "asmith02", "first_name": "Ann", "last_name": "Smith", "email": "ann.smith@example.edu"},
}


class FakeLDAPUserSearch:
    """Stands in for ColdFront's LDAPUserSearch, answering from DIRECTORY."""

    def __init__(self, user_search_string, search_by):
        pass

    def search_a_user(self, user_search_string=None, search_by="all_fields"):
        entry = DIRECTORY.get(user_search_string)
        return [entry] if entry else []


def make_choices():
    ProjectUserRoleChoiceFactory(name="User")
    ProjectUserStatusChoiceFactory(name="Active")
    ProjectUserStatusChoiceFactory(name="Removed")


def make_project_with_group(group):
    project = ProjectFactory()
    group_type = ProjectAttributeTypeFactory(
        name=UNIX_GROUP_ATTRIBUTE_NAME, attribute_type=PAttributeTypeFactory(name="Text")
    )
    ProjectAttributeFactory(project=project, proj_attr_type=group_type, value=group)
    return project


@patch("user_management.utils.LDAPUserSearch", FakeLDAPUserSearch)
class CreateProjectUserFromUsernameTests(TestCase):
    def setUp(self):
        make_choices()
        self.project = ProjectFactory()

    def test_a_username_the_directory_does_not_know_is_refused(self):
        with self.assertRaises(UserNotInDirectoryError):
            create_project_user_from_username("Chanyoung", self.project)

        self.assertFalse(User.objects.filter(username="Chanyoung").exists())
        self.assertFalse(ProjectUser.objects.filter(project=self.project).exists())

    def test_an_existing_user_the_directory_no_longer_knows_is_refused(self):
        UserFactory(username="clondo01")

        with self.assertRaises(UserNotInDirectoryError):
            create_project_user_from_username("clondo01", self.project)

        self.assertFalse(ProjectUser.objects.filter(project=self.project).exists())

    def test_a_new_user_the_directory_knows_is_created_with_their_details(self):
        project_user = create_project_user_from_username("jdoe01", self.project)

        self.assertEqual(project_user.status.name, "Active")
        self.assertEqual(project_user.role.name, "User")
        user = User.objects.get(username="jdoe01")
        self.assertEqual((user.first_name, user.last_name, user.email), ("Jane", "Doe", "jane.doe@example.edu"))


@patch("user_management.utils.LDAPUserSearch", FakeLDAPUserSearch)
class SyncProjectUsersFromExternalTests(TestCase):
    def setUp(self):
        make_choices()
        self.client_stub = UserManagementClient()
        patcher = patch("user_management.utils.get_client", return_value=self.client_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def put_in_group(self, group, *usernames):
        for username in usernames:
            self.client_stub.add_user_to_group(username, group)

    def test_skips_members_the_directory_does_not_know_and_adds_the_rest(self):
        project = make_project_with_group("lab_grp")
        self.put_in_group("lab_grp", "jdoe01", "Chanyoung")

        result = sync_project_users_from_external(project.pk)

        self.assertEqual(result["added"], ["jdoe01"])
        self.assertEqual(result["skipped"], ["Chanyoung"])
        self.assertTrue(ProjectUser.objects.filter(project=project, user__username="jdoe01").exists())
        self.assertFalse(User.objects.filter(username="Chanyoung").exists())

    def test_ignores_a_member_whose_username_could_not_be_read(self):
        """The Grouper client gives None for a member whose username it can't parse."""
        project = make_project_with_group("lab_grp")
        self.put_in_group("lab_grp", "jdoe01", None)

        result = sync_project_users_from_external(project.pk)

        self.assertEqual(result["added"], ["jdoe01"])
        self.assertEqual(result["skipped"], [])
        self.assertEqual(ProjectUser.objects.filter(project=project).count(), 1)

    def test_the_add_from_group_view_skips_members_the_directory_does_not_know(self):
        project = make_project_with_group("lab_grp")
        self.put_in_group("lab_grp", "jdoe01", "Chanyoung")
        request = RequestFactory().post(f"/add-group-members-from-external/{project.pk}/")
        request.user = UserFactory(username="rdms_admin", is_superuser=True)
        request._dont_enforce_csrf_checks = True

        response = add_group_members_from_external(request, project.pk)

        body = json.loads(response.content)
        self.assertEqual(body["members_added"], [{"username": "jdoe01"}])
        self.assertEqual(body["skipped"], [{"username": "Chanyoung", "reason": "not in the directory"}])
        self.assertFalse(User.objects.filter(username="Chanyoung").exists())

    def test_sync_all_reports_each_projects_additions_and_skips(self):
        first = make_project_with_group("first_grp")
        second = make_project_with_group("second_grp")
        self.put_in_group("first_grp", "jdoe01", "Chanyoung")
        self.put_in_group("second_grp", "asmith02", "clondo01")

        result = sync_all_project_users_from_external()

        self.assertEqual(result["added"], {first.title: ["jdoe01"], second.title: ["asmith02"]})
        self.assertEqual(result["skipped"], {first.title: ["Chanyoung"], second.title: ["clondo01"]})
        self.assertIn("skipped 2", result["message"])
