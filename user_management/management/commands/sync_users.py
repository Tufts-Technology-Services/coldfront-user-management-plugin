import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django_auth_ldap.backend import LDAPBackend

from coldfront.core.allocation.models import Allocation, AllocationUser
from coldfront.core.project.models import Project, ProjectUser

from user_management import utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = f"Sync group memberships between Coldfront and an external system. Groups must be defined in {'projects' if settings.MANAGE_GROUPS_AT_PROJECT_LEVEL else 'allocations'} attributes."

    def add_arguments(self, parser):
        parser.add_argument("-t", "--sync-to", help="Sync changes to external system", action="store_true")
        parser.add_argument("-u", "--username", help="Check specific username")
        parser.add_argument("-g", "--group", help="Check specific group")
        parser.add_argument(
            "-d", "--dry-run", help="Only show differences. Do not run any commands.", action="store_true"
        )
        #parser.add_argument("-x", "--no-header", help="Exclude header from output", action="store_true")
        #parser.add_argument("-f", "--format", help="json or csv output", default=None)
        #parser.add_argument("-o", "--output-file", help="Path to output file for saving group updates", required=True)

    def collate_project_user_data(self, group_attribute_name, group_specified=None):
        coldfront_project_users = []
        # get project users mapped to groups and projects
        projects_with_groups = Project.objects.filter(
            status__name="Active", projectattribute__proj_attr_type__name=group_attribute_name
        ).distinct()
        self.stdout.write("Found %d projects with groups." % projects_with_groups.count())
        for project in projects_with_groups:
            self.stdout.write("Processing project %s (ID: %s)..." % (project.title, project.pk))
            project_info = {"project": project.title, "project_id": project.pk, "groups": [], "users": []}
            # get groups from project attributes
            groups = utils.get_project_attribute_values_set(project, group_attribute_name)
            if group_specified and group_specified not in groups:
                logger.debug(
                    "  Skipping project %s due to group filter. Group '%s' not in project groups %s.",
                    project.title,
                    group_specified,
                    groups,
                )
                continue
            if len(groups) == 0:
                logger.debug("    Project %s does not have any groups. Nothing to add or remove.", project.title)
                continue
            logger.debug("    Groups from project attribute '%s': %s", group_attribute_name, groups)
            project_info["groups"] = list(groups)
            # get active project users
            project_users = ProjectUser.objects.filter(project=project, status__name="Active").select_related("user")
            project_info["users"] = list(project_users.values_list("user__username", flat=True))

            logger.debug("  Project PI: %s (ID: %s)", project.pi.username, project.pi.pk)
            project_info["users"].append(project.pi.username)
            coldfront_project_users.append(project_info)
            return coldfront_project_users

    def collate_allocation_user_data(self, group_attribute_name, group_specified=None):
        coldfront_allocation_users = []
        # get project users mapped to groups and projects
        allocations_with_groups = Allocation.objects.filter(
            status__name="Active", allocationattribute__allocation_attribute_type__name=group_attribute_name
        ).distinct()
        self.stdout.write("Found %d allocations with groups." % allocations_with_groups.count())
        for allocation in allocations_with_groups:
            self.stdout.write("Processing allocation %s (ID: %s)..." % (allocation.resources.first().name, allocation.pk))
            allocation_info = {
                "allocation": allocation.resources.first().name,
                "allocation_id": allocation.pk,
                "groups": [],
                "users": [],
            }
            # get groups from project attributes
            groups = set(allocation.get_attribute_list(group_attribute_name))
            if group_specified and group_specified not in groups:
                logger.debug(
                    "  Skipping allocation %s(%s) due to group filter. Group '%s' not in allocation groups %s.",
                    allocation.resources.first().name,
                    allocation.pk,
                    group_specified,
                    groups,
                )
                continue
            if len(groups) == 0:
                logger.debug("    Allocation %s(%s) does not have any groups. Nothing to add or remove.", 
                             allocation.resources.first().name, allocation.pk)
                continue
            logger.debug("    Groups from project attribute '%s': %s", group_attribute_name, groups)
            allocation_info["groups"] = list(groups)

            # get active project users
            allocation_users = AllocationUser.objects.filter(
                allocation=allocation, status__name="Active"
            ).select_related("user")
            allocation_info["users"] = list(allocation_users.values_list("user__username", flat=True))

            coldfront_allocation_users.append(allocation_info)
            return coldfront_allocation_users

    def collate_external_user_data(self, group_set):
        client = utils.get_client()
        external_users_and_groups = []
        for group in group_set:
            self.stdout.write("Querying external system for members of group %s..." % group)
            try:
                members = client.get_group_members(group)
            except Exception as e:
                self.stderr.write("Failed to get members of group %s: %s" % (group, e))
                continue
            external_users_and_groups.append({"group": group, "members": members})
        return external_users_and_groups

    def compare_coldfront_to_external(self, coldfront_users_and_groups, external_users_and_groups):
        differences = []
        external_group_dict = {g["group"]: set(g["members"]) for g in external_users_and_groups}
        for entry in coldfront_users_and_groups:
            alignment = "project" if "project" in entry else "allocation"
            groups = entry["groups"]
            users = set(entry["users"])
            for group in groups:
                external_members = external_group_dict.get(group, set())
                missing_from_external = users - external_members
                missing_from_coldfront = external_members - users
                if missing_from_external or missing_from_coldfront:
                    differences.append(
                        {
                            alignment: entry[alignment],
                            f"{alignment}_id": entry[f"{alignment}_id"],
                            "group": group,
                            "missing_from_external": list(missing_from_external),
                            "missing_from_coldfront": list(missing_from_coldfront),
                        }
                    )
                    logger.debug(
                        "Group %s: %d users to add, %d users to remove.",
                        group,
                        len(missing_from_external),
                        len(missing_from_coldfront),
                    )
        return differences

    def handle(self, *args, **options):
        username_specified = options.get("username", None)
        group_specified = options.get("group", None)
        dry_run = options.get("dry_run", False)
        #no_header = options.get("no_header", False)
        sync_to = options.get("sync_to", False)

        if username_specified:
            self.stdout.write("Filtering to username: %s" % username_specified)
        if group_specified:
            self.stdout.write("Filtering to group: %s" % group_specified)
        if dry_run:
            self.stdout.write("Dry run mode enabled. No changes will be made.")
        #if no_header:
       #     self.stdout.write("No header mode enabled. Header will be excluded from output.")

        # get list of groups from coldfront mapped to projects/allocations
        # determine whether to sync at the project or allocation level
        group_attribute_name = settings.UNIX_GROUP_ATTRIBUTE_NAME
        if settings.MANAGE_GROUPS_AT_PROJECT_LEVEL:
            self.stdout.write("Managing groups at the project level...")
            coldfront_users_and_groups = self.collate_project_user_data(group_attribute_name, group_specified)

        else:
            self.stdout.write("Managing groups at the allocation level...")
            # get allocation users mapped to groups and allocations
            coldfront_users_and_groups = self.collate_allocation_user_data(group_attribute_name, group_specified)

        group_set = set([n for sub in coldfront_users_and_groups for n in sub["groups"]])
        # query external system for members of each group
        external_users_and_groups = self.collate_external_user_data(group_set)

        # compare coldfront to external system and determine adds/removes
        differences = self.compare_coldfront_to_external(coldfront_users_and_groups, external_users_and_groups)

        if not dry_run:
            if sync_to:
                self.stdout.write("Syncing changes to external system...")
                client = utils.get_client()
                # sync coldfront users and groups to external system
                # for each difference, add users missing from external, remove users missing from coldfront
                for diff in differences:
                    for user in diff["missing_from_external"]:
                        if username_specified and user != username_specified:
                            logger.debug("  Skipping add of user %s due to username filter.", user)
                            continue
                        self.stdout.write("Adding user %s to group %s..." % (user, diff["group"]))
                        try:
                            client.add_user_to_group(user, diff["group"])
                        except IOError as e:
                            self.stdout.write("Failed to add user %s to group %s: %s" % (user, diff["group"], e))
                    for user in diff["missing_from_coldfront"]:
                        if username_specified and user != username_specified:
                            logger.debug("  Skipping remove of user %s due to username filter.", user)
                            continue
                        self.stdout.write("Removing user %s from group %s..." % (user, diff["group"]))
                        try:
                            client.remove_user_from_group(user, diff["group"])
                        except IOError as e:
                            self.stdout.write("Failed to remove user %s from group %s: %s" % (user, diff["group"], e))
            else:
                self.stdout.write("Syncing changes from external system...")
                # sync external group memberships to coldfront
                # for each difference, add users missing from coldfront, remove users missing from external
                for diff in differences:
                    difference_type = "project" if "project" in diff else "allocation"
                    if difference_type == "project":
                        # get the Project object
                        p = Project.objects.get(pk=diff["project_id"])
                        for user in diff["missing_from_coldfront"]:
                            if username_specified and user != username_specified:
                                logger.debug("  Skipping add of user %s due to username filter.", user)
                                continue
                            self.stdout.write("Adding user %s to project %s..." % (user, diff["project"]))
                            try:
                                # add the user to the Project
                                # create a ProjectUser object with status 'Active'
                                user_obj, created = User.objects.get_or_create(username=user)
                                if created:
                                    # populate user details from LDAP
                                    LDAPBackend().populate_user_from_ldap(user)

                                pu = ProjectUser(project=p, user=user_obj, status="Active")
                                pu.save()
                            except Exception as e:
                                self.stdout.write("Failed to add user %s to project %s: %s" % (user, diff["project"], e))

                        project_users = ProjectUser.objects.filter(project=p)
                        for user in diff["missing_from_external"]:
                            if username_specified and user != username_specified:
                                logger.debug("  Skipping remove of user %s due to username filter.", user)
                                continue
                            self.stdout.write("Removing user %s from project %s..." % (user, diff["project"]))
                            try:
                                # remove the user from the Project
                                for pu in project_users:
                                    if pu.user.username == user:
                                        pu.status = "Removed"
                                        pu.save()
                            except Exception as e:
                                self.stdout.write("Failed to remove user %s from project %s: %s" % (user, diff["project"], e))
                    else:  # allocation level
                        # get the Allocation object
                        a = Allocation.objects.get(pk=diff["allocation_id"])
                        for user in diff["missing_from_coldfront"]:
                            if username_specified and user != username_specified:
                                logger.debug("  Skipping add of user %s due to username filter.", user)
                                continue
                            self.stdout.write("Adding user %s to allocation %s..." % (user, diff["allocation"]))
                            try:
                                # add the user to the Allocation
                                # create an AllocationUser object with status 'Active'
                                user_obj, created = User.objects.get_or_create(username=user)
                                if created:
                                    # populate user details from LDAP
                                    LDAPBackend().populate_user_from_ldap(user)

                                au = AllocationUser(allocation=a, user=user_obj, status="Active")
                                au.save()
                            except Exception as e:
                                self.stdout.write("Failed to add user %s to allocation %s: %s" % (user, diff["allocation"], e))
                        allocation_users = AllocationUser.objects.filter(allocation=a)
                        for user in diff["missing_from_external"]:
                            if username_specified and user != username_specified:
                                logger.debug("  Skipping remove of user %s due to username filter.", user)
                                continue
                            self.stdout.write("Removing user %s from allocation %s..." % (user, diff["allocation"]))
                            try:
                                # remove the user from the Allocation
                                for au in allocation_users:
                                    if au.user.username == user:
                                        au.status = "Removed"
                                        au.save()
                            except Exception as e:
                                self.stdout.write(
                                    "Failed to remove user %s from allocation %s: %s" % (user, diff["allocation"], e)
                                )
            self.stdout.write("Sync complete.")
        else:
            self.stdout.write("Dry run complete. No changes were made.")
        return differences
