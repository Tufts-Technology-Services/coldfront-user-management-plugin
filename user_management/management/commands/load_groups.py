import csv
import json
import logging
import os

import coldfront.core.allocation.models as allocation_models
import coldfront.core.project.models as project_models
from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Associate groups with projects or allocations"

    def __init__(self):
        super().__init__()
        self.differences = {}  # to track changes made

    def add_arguments(self, parser):
        parser.add_argument(
            "-a",
            "--alignment",
            help="Set group alignment at 'project' or 'allocation' level",
            choices=["project", "allocation"],
            required=False,
        )
        parser.add_argument("-n", "--include-new", help="Include 'New' projects or allocations", action="store_true", default=False)
        parser.add_argument("-i", "--input-file", help="Path to input file containing group mappings", required=True)
        parser.add_argument("-o", "--output-file", help="Path to output file for saving group updates", required=True)
        parser.add_argument(
            "-d", "--dry-run", help="Only show differences. Do not run any commands.", action="store_true"
        )

    def process_csv_input_file(self, input_file):
        """
        Process the input file and return a dictionary of group mappings.
        The input file should be a CSV with two columns: 'name' and 'group'.
        """
        with open(input_file, mode="r", encoding="utf-8") as file:
            rows = csv.DictReader(file)
            return self.__parse_input_data(rows)

    def process_json_input_file(self, input_file):
        """
        Process the input file and return a dictionary of group mappings.
        The input file should be a JSON object with keys as names and values as groups.
        """
        with open(input_file, mode="r", encoding="utf-8") as file:
            data = json.load(file)
            return self.__parse_input_data(data)

    @staticmethod
    def __parse_input_data(rows):
        """
        Parse input data rows into a dictionary of group mappings.
        Each row should contain 'name', optional 'pi_username', and 'group'.
        """
        group_mappings = {}
        for row in rows:
            project = row.get("project")
            pi_username = row.get("pi_username")
            allocation_id = row.get("allocation_id")
            group = row.get("group")

            if group is None or group.strip() == "":
                logger.warning("Skipping row with empty group: %s", row)
                continue
            if allocation_id is not None and allocation_id.strip() != "":
                group_mappings[allocation_id.strip()] = group
            elif (project is None or project.strip() == "") and (pi_username is None or pi_username.strip() == ""):
                group_mappings[f"{project}_{pi_username}".lower().strip()] = group
            else:
                logger.warning("Skipping invalid row: %s", row)
        return group_mappings

    def get_project_attribute_type(self, group_attribute_name, dry_run):
        # check if the ProjectAttributeType exists
        project_attribute_type, created = project_models.ProjectAttributeType.objects.get_or_create(
            name=group_attribute_name,
            defaults={
                "attribute_type": project_models.AttributeType.objects.get(name="Text"),
                "has_usage": False,
                "is_required": False,
                "is_unique": False,
                "is_private": False,
                "is_changeable": True,
            },
        )
        if created and not dry_run:
            logger.info("Created ProjectAttributeType '%s'.", group_attribute_name)
        else:
            logger.info("ProjectAttributeType '%s' already exists.", group_attribute_name)
        return project_attribute_type

    def set_group_attribute_for_projects(self, project_attribute_type, group_mappings, include_new, dry_run):
        logger.info("Setting group attribute at the project level...")
        # get a list of projects
        projects = None
        if include_new:
            projects = project_models.Project.objects.filter(status__name__in=["Active", "New"])
        else:
            projects = project_models.Project.objects.filter(status__name="Active")
        logger.info("Found %d active projects.", projects.count())
        for project in projects:
            # get the group for the current project from the input file
            group_for_project = group_mappings.get(f"{project.title}_{project.pi.username}".lower().strip())
            if not group_for_project:
                logger.info("    No group mapping found for project %s in input file. Skipping.", project.title)
                continue

            # check if the current project has the group attribute defined
            project_attributes = project.projectattribute_set.filter(proj_attr_type=project_attribute_type)
            # todo: check if the AttributeType name is a unique value
            if project_attributes.exists():
                logger.info("  Project %s has group attribute defined.", project.title)
                # update if different than passed value, otherwise do nothing
                # todo: should have an option to not overwrite existing values
                if project_attributes.first().value == group_for_project:
                    logger.info("    Group attribute already set to %s. Skipping.", group_for_project)
                    self.differences["skipped"].append(
                        {
                            "mapping_key": f"{project.title}_{project.pi.username}".lower().strip(),
                            "project": project.title,
                            "project_pi": project.pi.username,
                            "group": group_for_project,
                            "new_group": group_for_project,
                        }
                    )
                    continue
                if not dry_run:
                    project_attributes.first().update(value=group_for_project)
                    logger.info("    Updated group attribute to %s for project %s.", group_for_project, project.title)
                # log changes
                self.differences["updated"].append(
                    {
                        "mapping_key": f"{project.title}_{project.pi.username}".lower().strip(),
                        "project": project.title,
                        "project_pi": project.pi.username,
                        "group": project_attributes.first().value,  # assuming only one attribute of this type per project
                        "new_group": group_for_project,
                    }
                )
            else:
                logger.info("  Project %s does not have group attribute defined.", project.title)

                if not dry_run:
                    # create the ProjectAttribute with the value from passed argument
                    pa = project_models.ProjectAttribute(
                        project=project, proj_attr_type=project_attribute_type, value=group_for_project
                    )
                    pa.save()
                    logger.info(
                        "    Created group attribute %s=%s for project %s.",
                        project_attribute_type.name,
                        group_for_project,
                        project.title,
                    )
                    self.differences["added"].append(
                        {
                            "mapping_key": f"{project.title}_{project.pi.username}".lower().strip(),
                            "project": project.title,
                            "project_pi": project.pi.username,
                            "group": "",
                            "new_group": group_for_project,
                        }
                    )

    def get_allocation_attribute_type(self, group_attribute_name, dry_run):
        # check if the AllocationAttributeType exists
        allocation_attribute_type, created = allocation_models.AllocationAttributeType.objects.get_or_create(
            name=group_attribute_name,
            defaults={
                "attribute_type": allocation_models.AttributeType.objects.get(name="Text"),
                "has_usage": False,
                "is_required": False,
                "is_unique": False,
                "is_private": False,
                "is_changeable": True,
            },
        )
        if created and not dry_run:
            logger.info("Created AllocationAttributeType '%s'.", group_attribute_name)
        else:
            logger.info("AllocationAttributeType '%s' already exists.", group_attribute_name)
        return allocation_attribute_type

    def set_group_attribute_for_allocations(self, allocation_attribute_type, group_mappings, include_new, dry_run):
        # get a list of allocations
        allocations = None
        if include_new:
            allocations = allocation_models.Allocation.objects.filter(status__name__in=["Active", "New"])
        else:
            allocations = allocation_models.Allocation.objects.filter(status__name="Active")
        logger.info("Found %d active allocations.", allocations.count())
        for allocation in allocations:
            # get the group for the current allocation from the input file
            group_for_allocation = group_mappings.get(str(allocation.pk))
            # check if the current allocation has the group attribute defined
            allocation_attributes = allocation.allocationattribute_set.filter(
                allocation_attribute_type=allocation_attribute_type
            )
            if allocation_attributes.exists():
                logger.info("  Allocation %s has group attribute defined.", allocation.project.title)
                # update if different than passed value, otherwise do nothing
                if allocation_attributes.first().value == group_for_allocation:
                    logger.info("    Group attribute already set to %s. Skipping.", group_for_allocation)
                    self.differences["skipped"].append(
                        {
                            "mapping_key": f"{allocation.project.title}_{allocation.pi.username}".lower().strip(),
                            "allocation": allocation.resources.first().name,
                            "allocation_id": allocation.pk,
                            "group": group_for_allocation,
                            "new_group": group_for_allocation,
                        }
                    )
                    continue
                if not dry_run:
                    allocation_attributes.first().update(value=group_for_allocation)
                    logger.info(
                        "    Updated group attribute to %s for allocation %s.",
                        group_for_allocation,
                        allocation.project.title,
                    )
                    # log changes
                    self.differences["updated"].append(
                        {
                            "mapping_key": f"{allocation.project.title}_{allocation.pi.username}".lower().strip(),
                            "allocation": allocation.resources.first().name,
                            "allocation_id": allocation.pk,
                            "group": allocation_attributes.first().value,
                            "new_group": group_for_allocation,
                        }
                    )
            else:
                logger.info(
                    "  Allocation %s(%s) does not have group attribute defined.", allocation.resources.first().name, allocation.pk
                )
                if not dry_run:
                    # create the AllocationAttribute with the value from passed argument
                    aa = allocation_models.AllocationAttribute(
                        allocation=allocation,
                        allocation_attribute_type=allocation_attribute_type,
                        value=group_for_allocation,
                    )
                    aa.save()
                    logger.info(
                        "    Created group attribute %s=%s for allocation %s.",
                        allocation_attribute_type.name,
                        group_for_allocation,
                        allocation.resource.name,
                    )
                    self.differences["added"].append(
                        {
                            "mapping_key": f"{allocation.project.title}_{allocation.pi.username}".lower().strip(),
                            "allocation": allocation.resources.first().name,
                            "allocation_id": allocation.pk,
                            "group": "",
                            "new_group": group_for_allocation,
                        }
                    )

    def handle_input_file(self, input_file):
        if not input_file:
            logger.error("Input file is required.")
            raise ValueError("Input file is required.")
        if input_file.endswith(".csv"):
            group_mappings = self.process_csv_input_file(input_file)
        elif input_file.endswith(".json"):
            group_mappings = self.process_json_input_file(input_file)
        else:
            logger.error("Unsupported input file format. Please provide a CSV or JSON file.")
            raise ValueError("Unsupported input file format. Please provide a CSV or JSON file.")
        if not group_mappings:
            logger.error("No valid group mappings found in input file.")
            raise ValueError("No valid group mappings found in input file.")
        logger.debug("Processed %d group mappings from input file.", len(group_mappings))
        return group_mappings

    def parse_alignment(self, alignment):
        default_alignment = "project" if settings.MANAGE_GROUPS_AT_PROJECT_LEVEL else "allocation"
        if alignment not in ["project", "allocation", None]:
            logger.error("Invalid alignment specified. Must be 'project' or 'allocation'.")
            raise ValueError("Invalid alignment specified. Must be 'project' or 'allocation'.")
        if alignment is None:
            alignment = default_alignment

        if alignment != default_alignment:
            logger.warning(
                "Specified alignment '%s' differs from default setting. Proceeding with specified alignment.", alignment
            )
        logger.info("Setting group alignment at the '%s' level.", alignment)
        return alignment

    def handle_differences(self, group_mappings, output_file):
        # compare differences with group mappings from input file, add any missing entries to 'skipped'
        input_keys = set(group_mappings.keys())
        processed_keys = set()
        for change_type in ["added", "updated", "skipped"]:
            for change in self.differences[change_type]:
                processed_keys.add(change["mapping_key"])
        # these input keys didn't match any existing projects/allocations
        missing_keys = input_keys - processed_keys
        for key in missing_keys:
            self.differences["skipped"].append({"mapping_key": key, "group": group_mappings[key]})
        logger.debug(
            "Processed %d changes: %d added, %d updated, %d skipped.",
            len(self.differences["added"]) + len(self.differences["updated"]) + len(self.differences["skipped"]),
            len(self.differences["added"]),
            len(self.differences["updated"]),
            len(self.differences["skipped"]),
        )
        # write differences to output file
        if output_file.endswith(".csv"):
            with open(output_file, mode="w", encoding="utf-8", newline="") as file:
                fieldnames = [
                    "mapping_key",
                    "project",
                    "project_pi",
                    "allocation",
                    "allocation_id",
                    "old_value",
                    "new_value",
                    "value",
                    "group",
                    "action",
                ]
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for change_type in ["added", "updated", "skipped"]:
                    for change in self.differences[change_type]:
                        change["action"] = change_type
                        writer.writerow(change)
                logger.info("Wrote differences to output file %s.", output_file)
        elif output_file.endswith(".json"):
            with open(output_file, mode="w", encoding="utf-8") as file:
                json.dump(self.differences, file, indent=4)
                logger.info("Wrote differences to output file %s.", output_file)

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        if dry_run:
            logger.info("Dry run mode enabled. No changes will be made.")

        input_file = options.get("input_file")
        group_mappings = self.handle_input_file(input_file)
        
        output_file = options.get("output_file")
        if not output_file:
            logger.error("Output file is required.")
            return
        # check if output file is writable/valid path
        if not os.access(os.path.dirname(output_file), os.W_OK):
            logger.error("Output file is not writable.")
        # processes a list of groups mapped to projects or allocations
        # determine whether to set attributes at the project or allocation level
        alignment = self.parse_alignment(options.get("alignment"))
        include_new = options.get("include_new", False)

        # initialize differences tracking
        self.differences = {"added": [], "updated": [], "skipped": []}  # to track changes made

        # processes a list of groups mapped to projects or allocations
        # determine whether to set attributes at the project or allocation level
        group_attribute_name = settings.UNIX_GROUP_ATTRIBUTE_NAME
        if alignment == "project":
            logger.info("Setting group attribute at the project level...")
            project_attribute_type = self.get_project_attribute_type(group_attribute_name, dry_run)
            self.set_group_attribute_for_projects(project_attribute_type, group_mappings, include_new, dry_run)


        else:
            logger.info("Setting group attribute at the allocation level...")
            allocation_attribute_type = self.get_allocation_attribute_type(group_attribute_name, dry_run)
            self.set_group_attribute_for_allocations(allocation_attribute_type, group_mappings, include_new, dry_run)
        logger.info("Group attribute update process complete.")

        self.handle_differences(group_mappings, output_file)
