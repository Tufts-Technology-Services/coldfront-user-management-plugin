from django.urls import path

from user_management import views


urlpatterns = [
    path(
        'get-group-members/<int:project_id>/',
        views.get_group_members,
        name='get-group-members',
    ),
    path(
        'add-group-members-from-external/<int:project_id>/',
        views.add_group_members_from_external,
        name='add-group-members-from-external',
    ),
]