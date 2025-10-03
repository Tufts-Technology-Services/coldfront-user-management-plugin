from unittest.mock import patch
from django.test import TestCase, override_settings
from coldfront.core.allocation.utils import set_allocation_user_status_to_error
from coldfront.core.test_helpers.factories import AllocationUserFactory
from user_management.tasks import (add_allocation_user_to_group, 
                                                     remove_allocation_user_from_group)


@override_settings(USER_MANAGEMENT_CLIENT_PATH="user_management/tests/helpers.py")
@override_settings(UNIX_GROUP_ATTRIBUTE_NAME="ad_group")
class AddAllocationUserToGroupTests(TestCase):
    def setUp(self):
        self.allocation_user = AllocationUserFactory()
        self.allocation_user.user.username = "testuser"

    @patch("user_management.tasks.AllocationUser")
    @patch("user_management.utils.add_user_to_group_set")
    def test_success(self, mock_add_user_to_group_set, mock_AllocationUser):
        self.allocation_user.status.name = "Active"
        self.allocation_user.allocation.status.name = "Active"
        self.allocation_user.allocation.get_attribute_list = lambda group_attr_name: ["group1", "group2"] if group_attr_name == "ad_group" else []
        mock_AllocationUser.objects.get.return_value = self.allocation_user
        mock_add_user_to_group_set.return_value = None
        _ = add_allocation_user_to_group(int(mock_AllocationUser.pk))
        mock_add_user_to_group_set.assert_called_once_with("testuser", {"group1", "group2"}, error_callback=set_allocation_user_status_to_error)

    @patch("user_management.tasks.AllocationUser")
    @patch("user_management.tasks.logger")
    def test_allocation_not_active(self, mock_logger, mock_AllocationUser):
        self.allocation_user.allocation.status.name = "New"
        mock_AllocationUser.objects.get.return_value = self.allocation_user
        success = add_allocation_user_to_group(self.allocation_user.pk)
        mock_logger.warning.assert_called_with("Allocation is not active. Will not add user")
        self.assertFalse(success)

    @patch("user_management.tasks.AllocationUser")
    @patch("user_management.tasks.logger")
    def test_user_status_new(self, mock_logger, mock_allocation_user):
        self.allocation_user.allocation.status.name = "Active"
        self.allocation_user.status.name = "New"
        mock_allocation_user.objects.get.return_value = self.allocation_user
        success = add_allocation_user_to_group(mock_allocation_user.pk)
        mock_logger.warning.assert_called_with("Allocation user status is not 'Active'. Will not add user.")
        self.assertFalse(success)

    @patch("user_management.tasks.AllocationUser")
    @patch("user_management.tasks.logger")
    def test_user_status_not_active(self, mock_logger, mock_allocation_user):
        self.allocation_user.status.name = "Removed"
        self.allocation_user.allocation.status.name = "Active"
        mock_allocation_user.objects.get.return_value = self.allocation_user
        success = add_allocation_user_to_group(mock_allocation_user.pk)
        mock_logger.warning.assert_called_with("Allocation user status is not 'Active'. Will not add user.")
        self.assertFalse(success)

    @patch("user_management.tasks.AllocationUser")
    @patch("user_management.tasks.logger")
    def test_no_groups(self, mock_logger, mock_allocation_user):
        self.allocation_user.allocation.get_attribute_list = lambda group_attr_name: []
        mock_allocation_user.objects.get.return_value = self.allocation_user
        success = add_allocation_user_to_group(mock_allocation_user.pk)
        mock_logger.info.assert_called_with("Allocation does not have any groups. Nothing to add")
        self.assertFalse(success)


@override_settings(USER_MANAGEMENT_CLIENT_PATH="user_management/tests/helpers.py")
@override_settings(UNIX_GROUP_ATTRIBUTE_NAME="ad_group")
class RemoveAllocationUserFromGroupTests(TestCase):
    def setUp(self):
        self.allocation_user = AllocationUserFactory()
        self.allocation_user.user.username = "testuser"
    
    @patch("user_management.utils.remove_user_from_group_set")
    @patch("user_management.utils.collect_other_allocation_user_groups")
    @patch("user_management.tasks.AllocationUser")
    def test_success(self, mock_allocation_user, mock_collect_other_allocation_user_groups, mock_remove_user_from_group_set):
        self.allocation_user.status.name = "Removed"
        self.allocation_user.allocation.status.name = "Active"
        self.allocation_user.allocation.get_attribute_list = lambda group_attr_name: ["group1", "group2"] if group_attr_name == "ad_group" else []       
        mock_allocation_user.objects.get.return_value = self.allocation_user
        mock_collect_other_allocation_user_groups.return_value = []
        remove_allocation_user_from_group(mock_allocation_user.pk)
        mock_collect_other_allocation_user_groups.assert_called_once_with(self.allocation_user.user, "ad_group", self.allocation_user.allocation.pk)
        mock_remove_user_from_group_set.assert_called_once_with("testuser", {"group1", "group2"}, error_callback=set_allocation_user_status_to_error)

    @patch("user_management.tasks.AllocationUser")
    @patch("user_management.tasks.logger")
    def test_allocation_not_active(self, mock_logger, mock_allocation_user):
        self.allocation_user.allocation.status.name = "New"
        mock_allocation_user.objects.get.return_value = self.allocation_user
        remove_allocation_user_from_group(mock_allocation_user.pk)
        mock_logger.warning.assert_called_with("Allocation is not active or pending. Will not remove user from group")

    @patch("user_management.tasks.AllocationUser")
    @patch("user_management.tasks.logger")
    def test_user_status_not_removed(self, mock_logger, mock_allocation_user):
        self.allocation_user.allocation.status.name = "Active"
        self.allocation_user.status.name = "Active"
        mock_allocation_user.objects.get.return_value = self.allocation_user
        remove_allocation_user_from_group(mock_allocation_user.pk)
        mock_logger.warning.assert_called_with("Allocation user status is not 'Removed'. Will not remove user from group.")

    @patch("user_management.tasks.AllocationUser")
    @patch("user_management.tasks.logger")
    def test_no_groups(self, mock_logger, mock_allocation_user):
        self.allocation_user.status.name = "Removed"
        self.allocation_user.allocation.status.name = "Active"
        self.allocation_user.allocation.get_attribute_list = lambda group_attr_name: []
        mock_allocation_user.objects.get.return_value = self.allocation_user
        remove_allocation_user_from_group(mock_allocation_user.pk)
        mock_logger.info.assert_called_with("Allocation does not have any groups. Nothing to remove")
