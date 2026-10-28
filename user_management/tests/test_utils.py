from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase

from user_management.tests.helpers import UserManagementClient
from user_management.utils import (
    AlreadyMemberError,
    GroupDoesNotExistError,
    NotMemberError,
    _add_user_to_group,
    _remove_user_from_group,
    add_user_to_group_set,
    remove_user_from_group_set,
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


class FailingClient:
    """
    A client whose changes all fail, as when the group service is down. `member` is what it says
    about membership, so the call under test gets as far as the failing change: an addition needs
    the user not to be a member yet, a removal needs them to be one.
    """

    def __init__(self, member):
        self.member = member

    def group_exists(self, group):
        return True

    def create_group(self, group):
        return True

    def user_in_group(self, user, group):
        return self.member

    def add_user_to_group(self, user, group):
        raise IOError("group service unavailable")

    def remove_user_from_group(self, user, group):
        raise IOError("group service unavailable")


class TestErrorCallback(TestCase):
    """callback_args are unpacked into the callback, so they must be a tuple: (pk,), not (pk)."""

    def test_add_failure_calls_the_callback_with_its_args(self):
        callback = MagicMock()
        with patch("user_management.utils.get_client", return_value=FailingClient(member=False)):
            add_user_to_group_set("alice", {"g1"}, error_callback=callback, callback_args=(7,))
        callback.assert_called_once_with(7)

    def test_remove_failure_calls_the_callback_with_its_args(self):
        callback = MagicMock()
        with patch("user_management.utils.get_client", return_value=FailingClient(member=True)):
            remove_user_from_group_set("alice", {"g1"}, error_callback=callback, callback_args=(7,))
        callback.assert_called_once_with(7)
