from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from coldfront.core.project.models import ProjectUser
from user_management.utils import get_project_group_members_from_external

@require_GET
@csrf_protect
@user_passes_test(lambda u: u.is_superuser)
def get_group_members(request, project_id) -> list[str]:
    members = set() 
    group, ext_members = get_project_group_members_from_external(project_id)
    project_users = ProjectUser.objects.filter(project_id=project_id, status__name="Active").distinct()
    if project_users.exists():
        for pu in project_users:
            members.add({"user": pu, "source_match": pu.user.username in ext_members})
    missing_members = ext_members - set(project_users.values_list("user__username", flat=True))
    return JsonResponse({"members": list(members), "group": group, "missing_users": list(missing_members)}, status=200)