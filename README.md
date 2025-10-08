# coldfront-user-management-plugin
Coldfront plugin for managing group membership

The User Management Plugin provides an interface for managing user group membership within the ColdFront system. It allows for the integration of external user management systems, such as Grouper, to handle group membership and access control.

## Installation
1. Install the plugin using uv:
   ```bash
   uv add coldfront-user-management-plugin@git+https://github.com/Tufts-Technology-Services/coldfront-user-management-plugin.git
   ```
2. Copy `user_management.py` to the `coldfront/config/plugins/` directory in your ColdFront project.
3. Update `coldfront/config/settings.py` with the following:
```python
plugin_configs['PLUGIN_USER_MANAGEMENT'] = 'plugins/user_management.py'
```
4. Add the following to your environment variables (e.g., in `/etc/coldfront/coldfront.env`):
```
# User Management Plugin Settings
PLUGIN_USER_MANAGEMENT=True
UNIX_GROUP_ATTRIBUTE_NAME=ad_group  # name of the group attribute that holds your unix group name
USER_MANAGEMENT_CLIENT_PATH=    # defaults to the included Grouper client; set to your custom client path if you implement your own
USER_MANAGEMENT_ENABLE_SIGNALS=True  # plugin won't listen to Coldfront signals unless this is True
MANAGE_GROUPS_AT_PROJECT_LEVEL=False  # if True, groups are managed at the project level; if False, at the allocation level
USER_MANAGEMENT_REMOVE_USERS_ON_PROJECT_ARCHIVE=False
```

## Implementing a New Client

To implement a new user management client, follow these steps:

1. Create a new Python module for your client that implements the `UserManagementClient` protocol in your module, 
providing methods for managing user groups and permissions.
2. Update the `USER_MANAGEMENT_CLIENT_PATH` setting in your ColdFront configuration to point to your new client module.

## Additional Information
## Relevant Signals
Coldfront uses emits signals to notify plugins of certain events. The User Management Plugin connects to several signals to manage user group membership based on project and allocation events. These include:
- `project_activate_user`
- `allocation_activate_user`
- `project_remove_user`
- `allocation_remove_user`
- `project_archive` (if configured to remove users on project archive)
These signals trigger tasks to add or remove users from groups as needed.

### ProjectAddUsersView#POST
the `project_activate_user` signal. 
The ProjectAddUsersView in the core project sends the signal when users are added to 
a project ("Active" or "New" state). Also sends `allocation_activate_user` for each selected active allocation in the project.

### ProjectRemoveUsersView#POST
sends the `project_remove_user` signal for each user removed from an "Active" or "New" project.
also sends `allocation_remove_user` for each "Active" user in  "Active", "New", or "Renewal Requested" allocations in the project.
You cannot remove the PI from a project.

### AllocationDetailView#POST
sends `allocation_activate`, then `allocation_activate_user` signal for all allocation users when the allocation moves from any state that is not
"Active" ("Removed", "Error", "PendingEULA", "DeclinedEula") to "Active".
sends the `allocation_disable`, then `allocation_remove_user` signal for all allocation users when the allocation moves to "Denied" or "Revoked"

### AllocationEULAView#POST
sends the `allocation_activate_user` signal for the allocation user when they accept the EULA

## AllocationAddUsersView#POST
sends the `allocation_activate_user` signal for each user added to an allocation in the "
"Active" state.

## AllocationRemoveUsersView#POST
remove "Removed" and "Error" users from "Active", "New", or "Renewal Requested" allocations
`allocation_remove_user` signal is sent for each user removed from the allocation.

## AllocationRenewView#POST
on the form, the user can choose to remove users from the allocation only, or from the project and all allocations.
in both cases, the `allocation_remove_user` signal is sent for each user removed from the allocation.

### ProjectArchiveProjectView
ProjectArchiveProjectView is a view that archives a project and sends the `project_archive` signal.

