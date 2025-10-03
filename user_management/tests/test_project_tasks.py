from unittest.mock import patch

from coldfront.core.test_helpers.factories import ProjectFactory, ProjectUserFactory, UserFactory
from django.test import TestCase, override_settings

from user_management.tasks import (
    add_project_user_to_group,
    remove_all_project_users_from_groups,
    remove_project_user_from_group,
)
from user_management.utils import set_project_user_status_to_pending


@override_settings(USER_MANAGEMENT_CLIENT_PATH="user_management/tests/helpers.py")
@override_settings(UNIX_GROUP_ATTRIBUTE_NAME="ad_group")
class AddProjectUserToGroupTests(TestCase):
    def setUp(self):
        self.project_user = ProjectUserFactory()
        self.project_user.user.username = "testuser"

    @patch("user_management.tasks.ProjectUser")
    @patch("user_management.utils.add_user_to_group_set")
    def test_success(self, mock_add_user_to_group_set, mock_project_user):
        self.project_user.status.name = "Active"
        self.project_user.project.status.name = "Active"
        self.project_user.project.get_attribute_list = (
            lambda group_attr_name: ["group1", "group2"] if group_attr_name == "ad_group" else []
        )
        mock_project_user.objects.get.return_value = self.project_user
        mock_add_user_to_group_set.return_value = None
        add_project_user_to_group(mock_project_user.pk)
        mock_add_user_to_group_set.assert_called_once_with(
            "testuser", {"group1", "group2"}, error_callback=set_project_user_status_to_pending
        )

    @patch("user_management.tasks.ProjectUser")
    @patch("user_management.tasks.logger")
    def test_project_not_active(self, mock_logger, mock_project_user):
        self.project_user.project.status.name = "Archived"
        mock_project_user.objects.get.return_value = self.project_user
        add_project_user_to_group(mock_project_user.pk)
        mock_logger.warning.assert_called_with("Project is not active. Will not add user")

    @patch("user_management.tasks.ProjectUser")
    @patch("user_management.tasks.logger")
    def test_user_status_not_active(self, mock_logger, mock_project_user):
        self.project_user.project.status.name = "Active"
        self.project_user.status.name = "Removed"
        mock_project_user.objects.get.return_value = self.project_user
        add_project_user_to_group(mock_project_user.pk)
        mock_logger.warning.assert_called_with("Project user status is not 'Active'. Will not add user.")

    @patch("user_management.tasks.ProjectUser")
    @patch("user_management.tasks.logger")
    def test_no_groups(self, mock_logger, mock_project_user):
        self.project_user.status.name = "Active"
        self.project_user.project.status.name = "Active"
        self.project_user.project.get_attribute_list = lambda group_attr_name: []
        mock_project_user.objects.get.return_value = self.project_user
        add_project_user_to_group(mock_project_user.pk)
        mock_logger.info.assert_called_with("Project does not have any groups. Nothing to add")


@override_settings(USER_MANAGEMENT_CLIENT_PATH="user_management/tests/helpers.py")
@override_settings(UNIX_GROUP_ATTRIBUTE_NAME="ad_group")
class RemoveProjectUserFromGroupTests(TestCase):
    def setUp(self):
        self.project_user = ProjectUserFactory()
        self.project_user.user.username = "testuser"

    @patch("user_management.utils.remove_user_from_group_set")
    @patch("user_management.utils.collect_other_project_user_groups")
    @patch("user_management.tasks.ProjectUser")
    def test_success(self, mock_project_user, mock_collect_other_project_user_groups, mock_remove_user_from_group_set):
        self.project_user.status.name = "Removed"
        self.project_user.project.status.name = "Active"
        self.project_user.project.get_attribute_list = (
            lambda group_attr_name: ["group1", "group2"] if group_attr_name == "ad_group" else []
        )
        mock_project_user.objects.get.return_value = self.project_user
        mock_collect_other_project_user_groups.return_value = set()
        remove_project_user_from_group(mock_project_user.pk)
        mock_collect_other_project_user_groups.assert_called_once_with(
            self.project_user.user, "ad_group", self.project_user.project.pk
        )
        mock_remove_user_from_group_set.assert_called_once_with(
            "testuser", {"group1", "group2"}, error_callback=set_project_user_status_to_pending
        )

    @patch("user_management.tasks.ProjectUser")
    @patch("user_management.tasks.logger")
    def test_project_not_active(self, mock_logger, mock_project_user):
        self.project_user.project.status.name = "Archived"
        mock_project_user.objects.get.return_value = self.project_user
        remove_project_user_from_group(mock_project_user.pk)
        mock_logger.warning.assert_called_with("Project is archived. Will not remove user from group")

    @patch("user_management.tasks.ProjectUser")
    @patch("user_management.tasks.logger")
    def test_user_status_not_removed(self, mock_logger, mock_project_user):
        self.project_user.project.status.name = "Active"
        self.project_user.status.name = "Active"
        mock_project_user.objects.get.return_value = self.project_user
        remove_project_user_from_group(mock_project_user.pk)
        mock_logger.warning.assert_called_with("Project user status is not 'Removed'. Will not remove user from group.")

    @patch("user_management.tasks.ProjectUser")
    @patch("user_management.tasks.logger")
    def test_no_groups(self, mock_logger, mock_project_user):
        self.project_user.status.name = "Removed"
        self.project_user.project.status.name = "Active"
        self.project_user.project.get_attribute_list = lambda group_attr_name: []
        mock_project_user.objects.get.return_value = self.project_user
        remove_project_user_from_group(mock_project_user.pk)
        mock_logger.info.assert_called_with("Project does not have any groups. Nothing to remove")


@override_settings(USER_MANAGEMENT_CLIENT_PATH="user_management/tests/helpers.py")
@override_settings(UNIX_GROUP_ATTRIBUTE_NAME="ad_group")
class RemoveAllUsersFromProjectGroupsTests(TestCase):
    def setUp(self):
        self.project = ProjectFactory()
        self.project.pi.username = "piuser"
        self.project_user1 = ProjectUserFactory(project=self.project, user=UserFactory(username="user1"))
        self.project_user2 = ProjectUserFactory(project=self.project, user=UserFactory(username="user2"))
        self.project_user3 = ProjectUserFactory(project=self.project, user=UserFactory(username="user3"))

    @patch("user_management.utils.remove_user_from_group_set")
    @patch("user_management.utils.collect_other_project_user_groups")
    @patch("user_management.tasks.Project")
    def test_success(self, mock_project, mock_collect_other_project_user_groups, mock_remove_user_from_group_set):
        self.project.status.name = "Archived"
        self.project.get_attribute_list = (
            lambda group_attr_name: ["group1", "group2"] if group_attr_name == "ad_group" else []
        )
        mock_project.objects.get.return_value = self.project
        mock_collect_other_project_user_groups.return_value = set()
        remove_all_project_users_from_groups(self.project.pk)
        self.assertEqual(mock_collect_other_project_user_groups.call_count, 4)  # 3 users + 1 PI
        self.assertEqual(mock_remove_user_from_group_set.call_count, 4)
        mock_remove_user_from_group_set.assert_any_call(
            "user1", {"group1", "group2"}, error_callback=set_project_user_status_to_pending
        )
        mock_remove_user_from_group_set.assert_any_call(
            "user2", {"group1", "group2"}, error_callback=set_project_user_status_to_pending
        )
        mock_remove_user_from_group_set.assert_any_call(
            "user3", {"group1", "group2"}, error_callback=set_project_user_status_to_pending
        )
        mock_remove_user_from_group_set.assert_any_call("piuser", {"group1", "group2"})

    @patch("user_management.tasks.Project")
    @patch("user_management.tasks.logger")
    def test_project_not_archived(self, mock_logger, mock_project):
        self.project.status.name = "Active"
        mock_project.objects.get.return_value = self.project
        remove_all_project_users_from_groups(self.project.pk)
        mock_logger.warning.assert_called_with("Project is not archived. Will not remove users from groups")

    @patch("user_management.tasks.Project")
    @patch("user_management.tasks.logger")
    def test_no_groups(self, mock_logger, mock_project):
        self.project.status.name = "Archived"
        self.project.get_attribute_list = lambda group_attr_name: []
        mock_project.objects.get.return_value = self.project
        remove_all_project_users_from_groups(self.project.pk)
        mock_logger.info.assert_called_with("Project does not have any groups. Nothing to remove")

    @patch("user_management.utils.remove_user_from_group_set")
    @patch("user_management.utils.collect_other_project_user_groups")
    @patch("user_management.tasks.Project")
    def test_no_groups_to_remove(
        self, mock_project, mock_collect_other_project_user_groups, mock_remove_user_from_group_set
    ):
        self.project.status.name = "Archived"
        self.project.get_attribute_list = (
            lambda group_attr_name: ["group1", "group2"] if group_attr_name == "ad_group" else []
        )
        mock_project.objects.get.return_value = self.project
        mock_collect_other_project_user_groups.return_value = {
            "group1",
            "group2",
        }  # all users belong to both groups in other active projects
        remove_all_project_users_from_groups(self.project.pk)
        self.assertEqual(mock_collect_other_project_user_groups.call_count, 4)  # 3 users + 1 PI
        mock_remove_user_from_group_set.assert_not_called()
