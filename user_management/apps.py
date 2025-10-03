# SPDX-FileCopyrightText: (C) ColdFront Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
import logging

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from user_management.user_management_client import UserManagementClient
from user_management.utils import _get_client_module

logger = logging.getLogger(__name__)


class UserManagementConfig(AppConfig):
    """
    Configuration for the user management plugin.
    This class initializes signal receivers based on settings and tests the user management client configuration."""

    name = "user_management"

    def ready(self):
        #UserManagementConfig.validate_settings()
        # tests whether the client has the appropriate configuration and any dependencies can be imported
        logger.debug("Testing UserManagementClient configuration...")
        _get_client_module().UserManagementClient.test_config()
        if not isinstance(_get_client_module().UserManagementClient, UserManagementClient):
            raise ImproperlyConfigured(
                "UserManagementClient implementation does not conform to the UserManagementClient protocol."
            )

        if settings.USER_MANAGEMENT_ENABLE_SIGNALS:
            logger.info("Initializing User Management Plugin signal receivers...")
            # pylint: disable=import-outside-toplevel
            from user_management.signals import init_signal_receivers
            # default is to manage group membership at the allocation level
            init_signal_receivers(
                settings.MANAGE_GROUPS_AT_PROJECT_LEVEL, settings.USER_MANAGEMENT_REMOVE_USERS_ON_PROJECT_ARCHIVE
            )
        else:
            logger.warning(
                "User Management Plugin signal receivers are disabled. No users will be added or removed from groups automatically."
            )

    @staticmethod
    def validate_settings():
        """
        Validates the settings related to user management.
        Raises ImproperlyConfigured if any setting is invalid.
        """
        bool_plugin_settings = [
            "USER_MANAGEMENT_ENABLE_SIGNALS",
            "MANAGE_GROUPS_AT_PROJECT_LEVEL",
            "USER_MANAGEMENT_REMOVE_USERS_ON_PROJECT_ARCHIVE"
        ]
        string_plugin_settings = [
            "UNIX_GROUP_ATTRIBUTE_NAME",
            "USER_MANAGEMENT_CLIENT_PATH",
        ]
        for s in bool_plugin_settings + string_plugin_settings:
            if not hasattr(settings, s):
                raise ImproperlyConfigured(f"{s} must be defined.")

        for b in bool_plugin_settings:
            if not isinstance(getattr(settings, b), bool):
                raise ImproperlyConfigured(f"{b} must be a boolean.")

        for st in string_plugin_settings:
            if not isinstance(getattr(settings, st), str) and getattr(settings, st) is not None:
                raise ImproperlyConfigured(f"{st} must be a string or None.")
