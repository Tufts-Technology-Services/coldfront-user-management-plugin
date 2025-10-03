import logging

from coldfront.core.allocation.models import AllocationUser
from coldfront.core.allocation.utils import set_allocation_user_status_to_error
from coldfront.core.project.models import Project, ProjectUser
from django.conf import settings

from user_management import utils

logger = logging.getLogger(__name__)


def add_allocation_user_to_group(user_pk):
    """
    Adds the user to all groups defined in the allocation's attributes. The name of the attribute
    that contains the groups is defined in the settings as 'UNIX_GROUP_ATTRIBUTE_NAME', defaulting to 'ad_group'.
    If the allocation is not active or the user status is not active, the function will log a warning and return.
    If the allocation does not have any groups defined, the function will log an info message and return.
    On error, the allocation user's status will be set to 'Error'.
    """
    group_attribute_name = settings.UNIX_GROUP_ATTRIBUTE_NAME

    allocation_user = AllocationUser.objects.get(pk=user_pk)
    if allocation_user.allocation.status.name != "Active":
        logger.warning("Allocation is not active. Will not add user")
        return False

    if allocation_user.status.name != "Active":
        logger.warning("Allocation user status is not 'Active'. Will not add user.")
        return False

    groups = set(allocation_user.allocation.get_attribute_list(group_attribute_name))
    logger.debug("DEBUG: groups from allocation attribute '%s': %s", group_attribute_name, groups)
    if len(groups) == 0:
        logger.info("Allocation does not have any groups. Nothing to add")
        return False
    logger.debug(
        "DEBUG: calling add_user_to_group_set for user %s and groups %s", allocation_user.user.username, groups
    )
    utils.add_user_to_group_set(
        allocation_user.user.username, groups, error_callback=set_allocation_user_status_to_error
    )  # for allocation: set_allocation_user_status_to_error(user_pk) on error
    return True


def add_project_user_to_group(user_pk):
    """
    Adds the user to all groups defined in the project's attributes. The name of the attribute
    that contains the groups is defined in the settings as 'UNIX_GROUP_ATTRIBUTE_NAME', defaulting to 'ad_group'.
    If the project is not active or the user status is not active, the function will log a warning and return.
    If the project does not have any groups defined, the function will log an info message and return.
    On error, the project user's status will be set to 'Error'.
    """
    group_attribute_name = settings.UNIX_GROUP_ATTRIBUTE_NAME

    project_user = ProjectUser.objects.get(pk=user_pk)
    if project_user.project.status.name != "Active":
        logger.warning("Project is not active. Will not add user")
        return

    if project_user.status.name != "Active":
        logger.warning("Project user status is not 'Active'. Will not add user.")
        return

    groups = set(project_user.project.get_attribute_list(group_attribute_name))
    if len(groups) == 0:
        logger.info("Project does not have any groups. Nothing to add")
        return

    utils.add_user_to_group_set(
        project_user.user.username, groups, error_callback=utils.set_project_user_status_to_pending
    )


def remove_allocation_user_from_group(user_pk):
    """
    Removes the user from all groups defined in the allocation's attributes. The name of the attribute
    that contains the groups is defined in the settings as 'UNIX_GROUP_ATTRIBUTE_NAME', defaulting to 'ad_group'.
    If the allocation is not active or pending, or if the user status is not 'Removed', the function will log a warning and return.
    If the allocation does not have any groups defined, the function will log an info message and return.
    The user will only be removed from groups they do not belong to in other active allocations.
    On error, the allocation user's status will be set to 'Error'.
    """
    group_attribute_name = settings.UNIX_GROUP_ATTRIBUTE_NAME

    allocation_user = AllocationUser.objects.get(pk=user_pk)
    # check allocation status
    if allocation_user.allocation.status.name not in [
        "Active",
        "Pending",
        "Inactive (Renewed)",
    ]:
        logger.warning("Allocation is not active or pending. Will not remove user from group")
        return
    # check allocation user status
    if allocation_user.status.name != "Removed":
        logger.warning("Allocation user status is not 'Removed'. Will not remove user from group.")
        return

    groups = allocation_user.allocation.get_attribute_list(group_attribute_name)
    if len(groups) == 0:
        logger.info("Allocation does not have any groups. Nothing to remove")
        return

    # Ensure we don't remove the user from groups they belong to in other active allocations.
    other_groups = utils.collect_other_allocation_user_groups(
        allocation_user.user, group_attribute_name, allocation_user.allocation.pk
    )

    group_diff = set(groups).difference(other_groups)

    if len(group_diff) == 0:
        logger.info(
            "No groups to remove. User may belong to these groups in other active allocations: %s",
            set(groups).intersection(other_groups),
        )
        return

    utils.remove_user_from_group_set(
        allocation_user.user.username, group_diff, error_callback=set_allocation_user_status_to_error
    )  # for allocation: set_allocation_user_status_to_error(user_pk) on error


def remove_project_user_from_group(user_pk):
    """
    Removes the user from all groups defined in the project's attributes. The name of the attribute
    that contains the groups is defined in the settings as 'UNIX_GROUP_ATTRIBUTE_NAME', defaulting to 'ad_group'.
    If the project is archived, the function will log a warning and return.
    If the user status is not 'Removed', the function will log a warning and return.
    If the project does not have any groups defined, the function will log an info message and return.
    The user will only be removed from groups they do not belong to in other active projects.
    On error, the project user's status will be set to 'Error'.
    """
    group_attribute_name = settings.UNIX_GROUP_ATTRIBUTE_NAME
    project_user = ProjectUser.objects.get(pk=user_pk)
    if project_user.project.status.name in [
        "Archived",
    ]:
        logger.warning("Project is archived. Will not remove user from group")
        return

    if project_user.status.name != "Removed":
        logger.warning("Project user status is not 'Removed'. Will not remove user from group.")
        return

    groups = project_user.project.get_attribute_list(group_attribute_name)
    if len(groups) == 0:
        logger.info("Project does not have any groups. Nothing to remove")
        return

    # Ensure we don't remove the user from groups they belong to in other active projects.
    other_groups = utils.collect_other_project_user_groups(
        project_user.user, group_attribute_name, project_user.project.pk
    )
    group_diff = set(groups).difference(other_groups)

    if len(group_diff) == 0:
        logger.info(
            "No groups to remove. User may belong to these groups in other active or new projects: %s", other_groups
        )
        return

    utils.remove_user_from_group_set(
        project_user.user.username, group_diff, error_callback=utils.set_project_user_status_to_pending
    )


def remove_all_project_users_from_groups(project_pk):
    """
    Removes all users from all groups defined in the project's attributes. The name of the attribute
    that contains the groups is defined in the settings as 'UNIX_GROUP_ATTRIBUTE_NAME', defaulting to 'ad_group'.
    This function is typically called when a project is archived.
    The user will only be removed from groups they do not belong to in other active projects.
    On error, the project user's status will be set to 'Error'.
    """
    group_attribute_name = settings.UNIX_GROUP_ATTRIBUTE_NAME
    project = Project.objects.get(pk=project_pk)
    if project.status.name != "Archived":
        logger.warning("Project is not archived. Will not remove users from groups")
        return

    groups = set(project.get_attribute_list(group_attribute_name))
    if len(groups) == 0:
        logger.info("Project does not have any groups. Nothing to remove")
        return

    project_users = ProjectUser.objects.filter(project__pk=project_pk)
    for project_user in project_users:
        # Ensure we don't remove the user from groups they belong to in other active projects.
        other_groups = utils.collect_other_project_user_groups(project_user.user, group_attribute_name, project_pk)
        group_diff = set(groups).difference(other_groups)

        if len(group_diff) == 0:
            logger.info(
                "No groups to remove for user %s. User may belong to these groups in other active or new projects: %s",
                project_user.user.username,
                other_groups,
            )
            continue
        utils.remove_user_from_group_set(
            project_user.user.username, group_diff, error_callback=utils.set_project_user_status_to_pending
        )

    # remove PI from project groups as well
    pi_user = project.pi
    other_groups = utils.collect_other_project_user_groups(pi_user, group_attribute_name, project_pk)
    group_diff = set(groups).difference(other_groups)
    if len(group_diff) == 0:
        logger.info(
            "No groups to remove for PI %s. User may belong to these groups in other active or new projects: %s",
            pi_user.username,
            other_groups,
        )
        return
    utils.remove_user_from_group_set(pi_user.username, group_diff)
