workspace.py

The abstract base class.

Responsible for:

Open
Close
Activate
Deactivate
Save session
Restore session



manager.py

Responsible for:

Open workspace
Close workspace
Switch workspace
Get active workspace



registry.py

Only stores registered workspaces.
It should never open or close workspaces.



session.py

Stores session information.

Example:

Active Workspace

Developer

Open Tabs

3

Terminal Sessions

2



state.py

Stores runtime state.

Example:

Workspace Active

True

Workspace Loading

False



models.py

Only data models.

No business logic.



events.py

Only event names.

Example:

WorkspaceOpened

WorkspaceClosed

WorkspaceActivated

WorkspaceChanged



module.py

Registers the Workspace module into EON's bootstrap system.



Workspace Module

Purpose:
Manage all EON workspaces.

Current Supported Workspaces

• Chat
• Developer (future)
• Creative (future)
• Automation (future)

Responsibilities

- Register workspaces
- Activate workspace
- Deactivate workspace
- Restore sessions
- Maintain workspace state

Non Responsibilities

- Code editing
- Terminal
- Git
- File system
- AI reasoning
