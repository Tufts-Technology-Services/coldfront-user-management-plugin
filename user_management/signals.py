import logging
from django_q.tasks import async_task

from coldfront.core.project.views import ProjectAddUsersView, ProjectRemoveUsersView
from coldfront.core.allocation.signals import allocation_activate_user, allocation_remove_user
from coldfront.core.allocation.views import AllocationAddUsersView, AllocationRemoveUsersView, AllocationRenewView
from coldfront.core.project.signals import project_activate_user, project_remove_user, project_archive

logger = logging.getLogger(__name__)


def init_signal_receivers(project_level=False, remove_on_archive=False):
    """
    Initialize signal receivers for user management.
    :param project_level: Boolean flag to determine if group management at the project or allocation level.
    :param remove_on_archive: Boolean flag to determine if users should be removed from groups on project archive.
    """

    # determines whether user groups are set at the 'Project' level or the 'Allocation' level.
    if project_level:  # project level
        logger.debug("Initializing project-level signal receivers for User Management...")
        # connect signals to project user management views
        project_activate_user.connect(
            activate_project_user, sender=ProjectAddUsersView, 
            dispatch_uid="ump_activate_project_user_1") # dispatch_uid to avoid duplicate connections
        project_remove_user.connect(
            remove_project_user, sender=ProjectRemoveUsersView, 
            dispatch_uid="ump_remove_project_user_1")
        
        if remove_on_archive:
            logger.warning("User Management is configured to remove users on project archive. This will remove all users from their groups when a project is archived.")
            project_archive.connect(
                remove_all_project_users,
                dispatch_uid="ump_archive_project_1")
            
    else:  # allocation level
        logger.debug("Initializing allocation-level signal receivers for User Management...")
        # connect signals to allocation user management views
        allocation_activate_user.connect(
            activate_allocation_user, sender=ProjectAddUsersView, 
            dispatch_uid="ump_activate_allocation_user_1")
        allocation_activate_user.connect(
            activate_allocation_user, sender=AllocationAddUsersView, 
            dispatch_uid="ump_activate_allocation_user_2")
        allocation_remove_user.connect(
            remove_allocation_user, sender=ProjectRemoveUsersView, 
            dispatch_uid="ump_remove_allocation_user_1")
        allocation_remove_user.connect(
            remove_allocation_user, sender=AllocationRemoveUsersView, 
            dispatch_uid="ump_remove_allocation_user_2")
        allocation_remove_user.connect(
            remove_allocation_user, sender=AllocationRenewView, 
            dispatch_uid="ump_remove_allocation_user_3")

        if remove_on_archive:
            logger.warning("User Management is configured to remove users on project archive. This will remove all users from their groups when a project is archived.")
            project_archive.connect(
                remove_all_project_users,
                dispatch_uid="ump_archive_project")

def activate_allocation_user(sender, **kwargs):
    user_pk = kwargs.get("allocation_user_pk")
    async_task(
        "coldfront.plugins.user_management.tasks.add_allocation_user_to_group", user_pk)


def remove_allocation_user(sender, **kwargs):
    user_pk = kwargs.get("allocation_user_pk")
    async_task(
        "coldfront.plugins.user_management.tasks.remove_allocation_user_from_group", user_pk)


def activate_project_user(sender, **kwargs):
    user_pk = kwargs.get("project_user_pk")
    async_task(
        "coldfront.plugins.user_management.tasks.add_project_user_to_group", user_pk)


def remove_project_user(sender, **kwargs):
    user_pk = kwargs.get("project_user_pk")
    async_task(
        "coldfront.plugins.user_management.tasks.remove_project_user_from_group", user_pk)


def remove_all_project_users(sender, **kwargs):
    project_pk = kwargs.get("project_pk")
    async_task(
        "coldfront.plugins.user_management.tasks.remove_all_project_users_from_groups", project_pk)
    