import importlib.util
import inspect
import logging
import sys
from pathlib import Path

from django.conf import settings

from django.contrib.auth.models import User

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project, ProjectUser, ProjectUserStatusChoice, ProjectUserRoleChoice
from coldfront.plugins.ldap_user_search.utils import LDAPUserSearch

from .user_management_client import UserManagementClient
from .constants import UNIX_GROUP_ATTRIBUTE_NAME

logger = logging.getLogger(__name__)


class AlreadyMemberError(Exception):
    pass


class NotMemberError(Exception):
    pass


class GroupDoesNotExistError(Exception):
    pass


def set_project_user_status_to_pending(project_user_pk):
    """Sets the status of the project user to 'Pending'.
    This is used when there is an error adding the user to a group. We want to
    set the status to 'Pending' so that we can retry adding the user to the group
    and to ensure that the user is not considered 'Active' in Coldfront, where
    additional actions may have unexpected error conditions.
    """
    user_obj = ProjectUser.objects.get(pk=project_user_pk)
    pending_status = ProjectUserStatusChoice.objects.get(name="Pending")
    user_obj.status = pending_status
    user_obj.save()


def get_project_attribute_values_set(project, attribute_name):
    attr = project.projectattribute_set.filter(proj_attr_type__name=attribute_name).all()
    return set(a.value for a in attr)


def _add_user_to_group(user: str, group: str, client: UserManagementClient) -> None:
    group_exists = client.group_exists(group)
    if not group_exists:
        logger.info("Creating group %s...", group)
        client.create_group(group)
    if client.user_in_group(group, user):
        raise AlreadyMemberError(f"user {user} is already a member of group {group}")
    else:
        client.add_user_to_group(user, group)


def _remove_user_from_group(user: str, group: str, client: UserManagementClient) -> None:
    group_exists = client.group_exists(group)
    if not group_exists:
        raise GroupDoesNotExistError(f"group {group} does not exist in grouper")
    if not client.user_in_group(group, user):
        raise NotMemberError(f"user {user} is not a member of group {group}")
    client.remove_user_from_group(user, group)


def add_user_to_group_set(user: str, groups: set[str], error_callback=None,
                          callback_args=None) -> None:
    client = get_client()
    # validate that groups is a set
    if not isinstance(groups, set):
        raise ValueError("groups must be a set of group names")
    successful_additions = []
    failed_additions = []
    for group in groups:
        try:
            _add_user_to_group(user, group, client)
        except AlreadyMemberError:
            failed_additions.append(group)
            logger.warning("User %s is already a member of group %s", user, group)
        # pylint: disable=broad-except
        except Exception as e:  # Catch all other exceptions
            failed_additions.append(group)
            logger.error("Failed adding user %s to group %s: %s", user, group, e)
            if error_callback:
                if callback_args:
                    error_callback(*callback_args)
                else:
                    error_callback()
        else:
            successful_additions.append(group)
            logger.info("Added user %s to group %s successfully", user, group)
    message = ""
    if not successful_additions and not failed_additions:
        message = f"No groups were provided to add user {user} to."
    if not successful_additions and failed_additions:
        message = f"Failed to add user {user} to groups [{', '.join(failed_additions)}]."
    if successful_additions and not failed_additions:
        message = f"User {user} added to groups [{', '.join(successful_additions)}] successfully."
    if successful_additions and failed_additions:
        message = f"User {user} added to groups [{', '.join(successful_additions)}] successfully. Failed to add user {user} to groups [{', '.join(failed_additions)}]."
    return {"message": message, "successful_additions": successful_additions, "failed_additions": failed_additions}


def remove_user_from_group_set(user: str, groups: set[str], 
                               error_callback=None, callback_args=None) -> None:
    client = get_client()
    # validate that groups is a set
    if not isinstance(groups, set):
        raise ValueError("groups must be a set of group names")
    for group in groups:
        try:
            _remove_user_from_group(user, group, client)
        except NotMemberError:
            logger.warning("User %s is not a member of group %s", user, group)
        except GroupDoesNotExistError:
            logger.warning("Group %s does not exist in grouper", group)
        # pylint: disable=broad-except
        except Exception as e:  # Catch all other exceptions
            logger.error("Failed removing user %s from group %s: %s", user, group, e)
            if error_callback:
                if callback_args:
                    error_callback(*callback_args)
                else:
                    error_callback()
        else:
            logger.info("Removed user %s from group %s successfully", user, group)


def collect_other_allocation_user_groups(user, group_attribute_name, current_allocation_id) -> list[str]:
    other_user_allocations = (
        Allocation.objects.filter(
            allocationuser__user=user,
            allocationuser__status__name="Active",
            status__name="Active",
            allocationattribute__allocation_attribute_type__name=group_attribute_name,
        )
        .exclude(pk=current_allocation_id)
        .distinct()
    )

    other_groups = []
    for a in other_user_allocations:
        other_groups.extend(a.get_attribute_list(group_attribute_name))
    return set(other_groups)


def collect_other_project_user_groups(user, group_attribute_name, current_project_id) -> set[str]:
    other_user_projects = (
        Project.objects.filter(
            projectuser__user=user,
            projectuser__status__name="Active",
            status__name="Active",
            projectattribute__proj_attr_type__name=group_attribute_name,
        )
        .exclude(pk=current_project_id)
        .distinct()
    )

    other_groups = []
    for p in other_user_projects:
        other_groups.extend(get_project_attribute_values_set(p, group_attribute_name))
    return set(other_groups)


def create_project_user_from_username(username, project, role='User', status='Active'):
    user_obj, created = User.objects.get_or_create(username=username)
    if created:
        # populate user details from LDAP
        user_search = LDAPUserSearch("", "")
        results = user_search.search_a_user(username, 'username_only')
        if not results:
            logger.error("User %s not found in LDAP. User will be created with default values.", username)
        else:
            user_info = results[0]
            user_obj.first_name = user_info.get('first_name', '')
            user_obj.last_name = user_info.get('last_name', '')
            user_obj.email = user_info.get('email', '')
            user_obj.save()
    
    pu_role = ProjectUserRoleChoice.objects.get(name=role)
    pu_status = ProjectUserStatusChoice.objects.get(name=status)
    project_user, created = ProjectUser.objects.get_or_create(
        user=user_obj,
        project=project,
        role=pu_role,
        status=pu_status
    )
    return project_user


def _get_client_module():
    default_path = Path(sys.modules["user_management"].__file__).parent / "grouper_user_management_client.py"
    path = Path(settings.USER_MANAGEMENT_CLIENT_PATH) if hasattr(settings, "USER_MANAGEMENT_CLIENT_PATH") and len(settings.USER_MANAGEMENT_CLIENT_PATH) > 0 else default_path
    module_name = path.stem

    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, path.as_posix())
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def get_client_class():
    """Returns an instance of the UserManagementClient subclass as specified in settings."""
    client_module = _get_client_module()
    classes = []
    for _, obj in inspect.getmembers(client_module, inspect.isclass):
        # Filter out imported classes and only include classes defined in this module
        if obj.__module__ == client_module.__name__ and issubclass(obj, UserManagementClient):
            classes.append(obj)
    if len(classes) != 1:
        raise ImportError(
            f"Expected exactly one UserManagementClient subclass in {client_module.__name__}, found {len(classes)}"
        )
    return classes[0]


def get_client() -> UserManagementClient:
    """Returns an instance of the UserManagementClient subclass as specified in settings."""
    client_class = get_client_class()
    return client_class()


def get_project_group_members_from_external(project_pk):
    """
    Get all members of the project's groups from the external system. This is a potentially long-running task that should be run asynchronously.
    """
    project = Project.objects.get(pk=project_pk)
    groups = get_project_attribute_values_set(project, UNIX_GROUP_ATTRIBUTE_NAME)
    if len(groups) == 0:
        logger.info("Project does not have any groups. Nothing to sync")
        raise ValueError("Project does not have any groups.")
    usernames = set()
    client = get_client()
    for group in groups:
         if not client.group_exists(group):
             logger.warning("Group %s does not exist in external system. Skipping group.", group)
             raise GroupDoesNotExistError(f"group {group} does not exist in external system")
         group_members = client.get_group_members(group)
         usernames.update(group_members)
    return groups, usernames