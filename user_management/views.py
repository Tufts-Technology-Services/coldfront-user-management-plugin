from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from user_management.utils import get_project_group_members_from_external

@require_GET
@csrf_protect
@user_passes_test(lambda u: u.is_superuser)
def get_group_members(request, project_id) -> list[str]:
    groups, members = get_project_group_members_from_external(project_id)
    return JsonResponse({"members": list(members), "groups": list(groups)}, status=200)