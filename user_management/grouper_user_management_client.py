import importlib
import logging
import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class UserManagementClient:
    """
    Implements Coldfront UserManagementClientInterface using Grouper.
    """

    def __init__(self):
        try:
            grouper_client = importlib.import_module("grouper_client")
            self.client = grouper_client.GrouperClient(*self.get_config().values())
        except Exception as e:
            raise ImproperlyConfigured("Grouper client library is not installed. Please install it.") from e

    @staticmethod
    def get_config():
        """
        Retrieves the configuration for the Grouper client from Django settings.
        """
        return {
            "api_url": os.getenv("GROUPER_API_URL"),
            "entity_id": os.getenv("GROUPER_ENTITY_ID"),
            "key_path": os.getenv("GROUPER_KEY_PATH"),
            "group_stem": os.getenv("GROUPER_GROUP_STEM"),
        }

    @staticmethod
    def test_config():
        """
        Tests whether the Grouper client is properly configured by checking for necessary settings
        and attempting to import the Grouper client library.
        Raises ImproperlyConfigured if any configuration is missing or incorrect."""
        try:
            _ = importlib.import_module("grouper_client")
        except Exception as e:
            raise ImproperlyConfigured("Grouper client library is not installed. Please install it.") from e
        config = UserManagementClient.get_config()
        if not config["api_url"] or not config["entity_id"] or not config["key_path"] or not config["group_stem"]:
            raise ImproperlyConfigured("Grouper client is not properly configured. Please check your settings.")

    def add_user_to_group(self, user, group):
        try:
            r = self.client.add_member_to_group(group, user)
            logger.debug("Grouper add_member_to_group response: %s", r)
            return True
        except IOError as e:
            logger.error("Failed to add user %s to group %s: %s", user, group, e)
            return False

    def remove_user_from_group(self, user, group):
        try:
            r = self.client.remove_member_from_group(group, user)
            logger.debug("Grouper remove_member_from_group response: %s", r)
            return True
        except IOError as e:
            logger.error("Failed to remove user %s from group %s: %s", user, group, e)
            return False

    def user_in_group(self, user, group):
        try:
            return self.client.is_user_in_group(group, user)
        except IOError as e:
            logger.error("Failed to check if user %s is in group %s: %s", user, group, e)
            return False

    def group_exists(self, group):
        try:
            return self.client.group_exists(group)
        except IOError as e:
            logger.error("Failed to check if group %s exists: %s", group, e)
            return False

    def get_group_members(self, group):
        try:
            return self.client.get_group_members(group).values()
        except IOError as e:
            logger.error("Failed to get members of group %s: %s", group, e)
            return []

    def create_group(self, group):
        try:
            self.client.create_group(group)
            return True
        except IOError as e:
            logger.error("Failed to create group %s: %s", group, e)
            return False
