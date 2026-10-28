"""
Django settings for running this plugin's tests: ColdFront's own settings, with the plugin
installed, an in-memory database, and the plugin's settings (see user_management.py) given test
values. Selected by [tool.pytest.ini_options] in pyproject.toml.

Tests that need a different client or group attribute override them with override_settings.
"""

from coldfront.config.settings import *  # noqa: F403

INSTALLED_APPS += ["user_management"]  # noqa: F405

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

UNIX_GROUP_ATTRIBUTE_NAME = "ad_group"
# the in-memory stand-in for Grouper, rather than the real client
USER_MANAGEMENT_CLIENT_PATH = "user_management/tests/helpers.py"
# off, so creating test data doesn't reach the client through the signal handlers
USER_MANAGEMENT_ENABLE_SIGNALS = False
MANAGE_GROUPS_AT_PROJECT_LEVEL = False
USER_MANAGEMENT_REMOVE_USERS_ON_PROJECT_ARCHIVE = False
