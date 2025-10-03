import pytest
from django.test import TestCase

from user_management.tests.helpers import UserManagementClient
from user_management.utils import (
    AlreadyMemberError,
    GroupDoesNotExistError,
    NotMemberError,
    _add_user_to_group,
    _remove_user_from_group,
)


class TestUserManagementUtils(TestCase):
    def test_add_user_to_group_creates_group_and_adds_user(self):
        client = UserManagementClient()
        user = "alice"
        group = "testgroup"
        # Group does not exist yet
        assert not client.group_exists(group)
        _add_user_to_group(user, group, client)
        # Group should be created
        assert client.group_exists(group)
        # User should be added
        assert client.user_in_group(user, group)

    def test_add_user_to_group_raises_already_member_error(self):
        client = UserManagementClient()
        user = "bob"
        group = "testgroup2"
        client.create_group(group)
        client.add_user_to_group(user, group)
        # User is already a member
        with pytest.raises(AlreadyMemberError):
            _add_user_to_group(user, group, client)

    def test_add_user_to_group_adds_user_to_existing_group(self):
        client = UserManagementClient()
        user = "carol"
        group = "testgroup3"
        client.create_group(group)
        # User not in group yet
        _add_user_to_group(user, group, client)
        assert client.user_in_group(user, group)

    def test_remove_user_from_group_raises_not_member_error(self):
        client = UserManagementClient()
        user = "dave"
        group = "testgroup4"
        client.create_group(group)
        # User is not a member
        with pytest.raises(NotMemberError):
            _remove_user_from_group(user, group, client)

    def test_remove_user_from_group_removes_user(self):
        client = UserManagementClient()
        user = "eve"
        group = "testgroup5"
        client.create_group(group)
        client.add_user_to_group(user, group)
        # User is a member
        assert client.user_in_group(user, group)
        _remove_user_from_group(user, group, client)
        assert not client.user_in_group(user, group)

    def test_remove_user_from_group_raises_group_does_not_exist_error(self):
        client = UserManagementClient()
        user = "frank"
        group = "nonexistentgroup"
        # Group does not exist
        with pytest.raises(GroupDoesNotExistError):
            _remove_user_from_group(user, group, client)
