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
    help = "Gather information about projects or allocations to help set group attributes"

    def add_arguments(self, parser):
        parser.add_argument(
            "-a",
            "--alignment",
            help="Set group alignment at 'project' or 'allocation' level",
            choices=["project", "allocation"],
            required=False,
        )
        parser.add_argument("-o", "--output-file", help="Path to output file for saving group updates", required=True)
        parser.add_argument("-f", "--format", help="json or csv output", default=None)
        parser.add_argument(
            "-v", "--verbosity", help="Set the verbosity level (0=ERROR, 1=WARNING, 2=INFO, 3=DEBUG)", default=2
        )

    @staticmethod
    def set_verbosity(level):
        """Set the logging verbosity level."""
        level = int(level)
        root_logger = logging.getLogger("")
        if level == 0:
            root_logger.setLevel(logging.ERROR)
        elif level == 2:
            root_logger.setLevel(logging.INFO)
        elif level == 3:
            root_logger.setLevel(logging.DEBUG)
        else:
            root_logger.setLevel(logging.WARNING)

    @staticmethod
    def parse_alignment(alignment):
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

    def handle_output(self, rows: list[dict], output_file: str, output_format: str) -> None:
        # write differences to output file
        if output_format == "csv" or (output_format != "json" and output_file.endswith(".csv")):
            with open(output_file, mode="w", encoding="utf-8", newline="") as file:
                fieldnames = rows[0].keys() if rows else []
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
                logger.info("Wrote to csv output file %s.", output_file)
        elif output_format == "json" or (output_format != "csv" and output_file.endswith(".json")):
            with open(output_file, mode="w", encoding="utf-8") as file:
                json.dump(rows, file, indent=4)
                logger.info("Wrote to json output file %s.", output_file)

    def get_group_attribute_info_for_projects(self, group_attribute_name: str) -> list[dict]:
        logger.info("Getting group attribute info at the project level...")
        info = []
        # get a list of projects
        projects = project_models.Project.objects.filter(status__name="Active")
        logger.info("Found %d active projects.", projects.count())
        for project in projects:
            # check if the current project has the group attribute defined
            project_attributes = project.projectattribute_set.filter(project_attribute_type__name=group_attribute_name)
            if project_attributes.exists():
                logger.info("  Project %s has group attribute defined.", project.title)
                info.append(
                    {
                        "project": project.title,
                        "project_pi": project.pi.username,
                        "group": project_attributes.first().value,  # assuming only one attribute of this type per project
                    }
                )
            else:
                logger.info("  Project %s does not have group attribute defined.", project.title)
                info.append(
                    {
                        "project": project.title,
                        "project_pi": project.pi.username,
                        "group": "",
                    }
                )
        return info

    def get_group_attribute_info_for_allocations(self, group_attribute_name: str) -> list[dict]:
        logger.info("Getting group attribute info at the allocation level...")
        info = []
        # get a list of allocations
        allocations = allocation_models.Allocation.objects.filter(status__name="Active")
        logger.info("Found %d active allocations.", allocations.count())
        for allocation in allocations:
            # check if the current allocation has the group attribute defined
            allocation_attributes = allocation.allocationattribute_set.filter(
                allocation_attribute_type__name=group_attribute_name
            )
            if allocation_attributes.exists():
                logger.info("  Allocation %s has group attribute defined.", allocation.project.title)
                info.append(
                    {
                        "project": allocation.project.title,
                        "project_pi": allocation.pi.username,
                        "allocation": allocation.resource.name,
                        "allocation_id": allocation.pk,
                        "group": allocation_attributes.first().value,  # assuming only one attribute of this type per allocation
                    }
                )

            else:
                logger.info(
                    "  Allocation %s(%s) does not have group attribute defined.", allocation.name, allocation.pk
                )
                info.append(
                    {
                        "project": allocation.project.title,
                        "project_pi": allocation.pi.username,
                        "allocation": allocation.resource.name,
                        "allocation_id": allocation.pk,
                        "group": "",
                    }
                )
        return info

    def handle(self, *args, **options):
        self.set_verbosity(options["verbosity"])

        output_file = options.get("output_file")
        if not output_file:
            logger.error("Output file is required.")
            return
        # check if output file is writable/valid path
        if not os.access(os.path.dirname(output_file), os.W_OK):
            logger.error("Output file is not writable.")

        # determine whether to get attributes at the project or allocation level
        alignment = self.parse_alignment(options.get("alignment"))

        # initialize differences tracking
        info = []

        # processes a list of groups mapped to projects or allocations
        # determine whether to set attributes at the project or allocation level
        group_attribute_name = settings.UNIX_GROUP_ATTRIBUTE_NAME
        if alignment == "project":
            logger.info("Getting group attribute info at the project level...")

            info = self.get_group_attribute_info_for_projects(group_attribute_name)

        else:
            logger.info("Getting group attribute info at the allocation level...")
            info = self.get_group_attribute_info_for_allocations(group_attribute_name)

        # write differences to output file
        self.handle_output(info, output_file, options.get("format"))
        logger.info("Group attribute info gathering complete.")
