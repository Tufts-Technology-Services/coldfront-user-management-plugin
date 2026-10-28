from unittest.mock import MagicMock

from user_management.grouper_user_management_client import UserManagementClient


def make_adapter():
    """The Grouper adapter around a mock grouper_client, skipping __init__'s connection setup."""
    adapter = UserManagementClient.__new__(UserManagementClient)
    adapter.client = MagicMock()
    return adapter


def test_user_in_group_passes_the_library_its_own_argument_order():
    """The plugin's interface is (user, group); grouper_client's is_user_in_group is (group_name, username)."""
    adapter = make_adapter()

    adapter.user_in_group("alice", "hpc-group")

    adapter.client.is_user_in_group.assert_called_once_with("hpc-group", "alice")


def test_add_and_remove_pass_the_group_first():
    adapter = make_adapter()

    adapter.add_user_to_group("alice", "hpc-group")
    adapter.remove_user_from_group("alice", "hpc-group")

    adapter.client.add_members_to_group.assert_called_once_with("hpc-group", ["alice"])
    adapter.client.remove_members_from_group.assert_called_once_with("hpc-group", ["alice"])
