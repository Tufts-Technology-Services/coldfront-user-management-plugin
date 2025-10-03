this readme file should describe the user management plugin system and how to implement a new client.

another at the repository root should describe how to deploy the plugin.

there should also be a user_management.py file at the root to put in coldfront/config/plugins/

# User Management Plugin

The User Management Plugin provides an interface for managing user groups and permissions within the ColdFront system. It allows for the integration of external user management systems, such as Grouper, to handle group membership and access control.

## Implementing a New Client

To implement a new user management client, follow these steps:

1. Create a new Python module for your client that implements the `UserManagementClient` protocol in your module, 
providing methods for managing user groups and permissions.
2. Update the `USER_MANAGEMENT_CLIENT_PATH` setting in your ColdFront configuration to point to your new client module.

## Relevant Signals
The plugin connects to several signals to manage user group membership based on project and allocation events. These include:
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
ProjectArchiveProjectView is a view that archives a project and sends 
the `project_archive` signal. 

If the setting USER_MANAGEMENT_REMOVE_USERS_ON_PROJECT_ARCHIVE is set to True, 
the plugin will connect to the project_archive signal and remove all users 
from their groups when a project is archived.

The ProjectArchiveProjectView in the core project sends the signal. It
also sets all "Active" allocations to "Expired" for the archived project.

### project_update Signal
Sent on successful POST of ProjectUpdateView.

### project_new Signal
Sent on successful POST of ProjectCreateView.

### allocation_new Signal
Sent on successful POST of AllocationCreateView.

### allocation_change_approved Signal
AllocationChangeDetailView sends this signal when a change request is approved.

### allocation_change_created Signal
AllocationChangeView sends this signal when a change request is submitted.



