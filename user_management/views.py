from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from coldfront.core.project.models import ProjectUser, Project
from user_management.utils import create_project_user_from_username, get_project_group_members_from_external

@require_GET
@csrf_protect
@user_passes_test(lambda u: u.is_superuser)
def get_group_members(request, project_id) -> list[str]:
    members = [] 
    group, ext_members = get_project_group_members_from_external(project_id)
    project_users = ProjectUser.objects.filter(project_id=project_id, status__name="Active").distinct()
    if project_users.exists():
        for pu in project_users:
            members.append({"user": {"username": pu.user.username, "first_name": pu.user.first_name, "last_name": pu.user.last_name, "email": pu.user.email}, "source_match": pu.user.username in ext_members})
    missing_members = ext_members - set(project_users.values_list("user__username", flat=True))
    return JsonResponse({"members": members, "group": group, "missing_users": list(missing_members)}, status=200)


@require_POST
@csrf_protect
@user_passes_test(lambda u: u.is_superuser)
def add_group_members_from_external(request, project_id) -> list[str]:
    members = [] 
    group, ext_members = get_project_group_members_from_external(project_id)
    project_users = ProjectUser.objects.filter(project_id=project_id, status__name="Active").distinct()
    missing_members = ext_members - set(project_users.values_list("user__username", flat=True))
    project = Project.objects.get(pk=project_id)
    for username in missing_members:
        members.append({"username": username})
        create_project_user_from_username(username, project, role='User', status='Active')
    return JsonResponse({"members_added": members, "group": group}, status=200)