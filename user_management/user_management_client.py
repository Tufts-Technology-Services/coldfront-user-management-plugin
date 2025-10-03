from typing import Protocol, runtime_checkable


@runtime_checkable
class UserManagementClient(Protocol):
    """
    Protocol for user management clients.
    This protocol defines the methods that any user management client must implement to manage user groups.
    1. get_config: Retrieve configuration settings.
    2. test_config: Test the configuration for correctness.
    3. add_user_to_group: Add a user to a specified group.
    4. remove_user_from_group: Remove a user from a specified group.
    5. user_in_group: Check if a user is a member of a specified group.
    6. group_exists: Check if a specified group exists.
    7. get_group_members: Retrieve the members of a specified group.
    8. create_group: Create a new group.
    """
    @staticmethod
    def get_config() -> dict: ...

    @staticmethod
    def test_config() -> None: ...

    def add_user_to_group(self, user: str, group: str) -> bool: ...

    def remove_user_from_group(self, user: str, group: str) -> bool: ...

    def user_in_group(self, user: str, group: str) -> bool: ...

    def group_exists(self, group: str) -> bool: ...

    def get_group_members(self, group: str) -> list[str]: ...

    def create_group(self, group: str) -> bool: ...
