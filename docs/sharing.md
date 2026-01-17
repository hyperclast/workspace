# Current Sharing Model (Three-Tier Access Control)

This document describes Hyperclast's current sharing and permissions architecture.

## Overview

The system uses an **additive (union) access model** with three independent tiers. Access is granted if **ANY** condition is true:

```
User can access a Page if:
  ├── Tier 0: User is an org admin (always has access)
  ├── Tier 1: User is a member of the page's project's org (when org_members_can_access=True)
  ├── Tier 2: User is an editor of the page's project
  └── Tier 3: User is an editor of the page (NEW)
```

## Organizational Hierarchy

```
Organization
    └── Project (belongs to one org)
            └── Page (belongs to one project)
```

## Tier 0: Org Admin Access

**How it works:**

- Org admins always have full access to all projects and pages in their org
- This tier takes precedence over `org_members_can_access` setting
- Admin role is set via `OrgMember.role = 'admin'`

## Tier 1: Organization-Level Access

**How it works:**

- Users are members of organizations via `OrgMember` join table
- Org members have a role: `admin` or `member`
- Being an org member grants access to projects where `org_members_can_access=True`

**Roles:**
| Role | Data Access | Can Manage Org |
|------|-------------|----------------|
| `member` | Projects with org_members_can_access=True | No |
| `admin` | All projects/pages in org | Yes (settings, members, delete) |

**Key points:**

- Access can be restricted per-project via `org_members_can_access=False`
- Role only affects org management capabilities, not data access
- Domain-based auto-assignment: Users with company emails auto-join org by domain

## Tier 2: Project-Level Access (External Collaborators)

**How it works:**

- Users can be added as "editors" to specific projects via `ProjectEditor` join table
- Enables sharing with people outside the organization
- Project editors get access to ALL pages within that project

**Adding project editors:**

1. If user exists → Add directly to `project.editors` with specified role
2. If user doesn't exist → Create `ProjectInvitation` with role and send email

**Editor Roles:**

| Role     | View Pages | Edit Pages | Manage Editors |
| -------- | :--------: | :--------: | :------------: |
| `viewer` |     ✓      |            |                |
| `editor` |     ✓      |     ✓      |       ✓        |

## Tier 3: Page-Level Access (NEW)

**How it works:**

- Users can be added as "editors" to specific pages via `PageEditor` join table
- Enables sharing individual pages without giving access to the entire project
- Page editors see the project in their sidenav, but only pages they have access to

**Adding page editors:**

1. If user exists → Add directly to `page.editors` with specified role
2. If user doesn't exist → Create `PageInvitation` with role and send email

**Editor Roles:**

| Role     | View Page | Edit Page | Manage Editors |
| -------- | :-------: | :-------: | :------------: |
| `viewer` |     ✓     |           |                |
| `editor` |     ✓     |     ✓     |       ✓        |

**Key points:**

- Default role for new page editors: `viewer` (read-only)
- Users with only page-level access see `access_source="page_only"` on the project
- Projects list API filters pages based on user's access level
- Page editors can be added/removed via SharePageModal

## Permission Matrix

| Action                     | Org Admin | Org Member | Project Editor | Project Viewer | Page Editor | Page Viewer |
| -------------------------- | :-------: | :--------: | :------------: | :------------: | :---------: | :---------: |
| View page                  |     ✓     |     ✓      |       ✓        |       ✓        |      ✓      |      ✓      |
| Edit page                  |     ✓     |     ✓      |       ✓        |                |      ✓      |             |
| Create pages in project    |     ✓     |     ✓      |       ✓        |                |             |             |
| Delete page                |           |            |                |                |             |             |
| Modify project             |     ✓     |     ✓      |       ✓        |                |             |             |
| Delete project             |           |            |                |                |             |             |
| Add/remove project editors |     ✓     |     ✓      |       ✓        |                |             |             |
| Add/remove page editors    |     ✓     |     ✓      |       ✓        |                |      ✓      |             |
| Manage access codes        |     ✓     |     ✓      |       ✓        |                |      ✓      |             |

**Note:** Page and project deletion is creator-only, regardless of role.

## Invitation System

### Project Invitations

- Created when adding non-existent user as project editor
- Contains: email, secure token, expiry date, **role**
- Auto-accepts on login if email matches
- Stores in session for signup flow

### Page Invitations

- Created when adding non-existent user as page editor
- Contains: email, secure token, expiry date, **role**
- Auto-accepts on login if email matches
- Creates `PageEditor` with invitation's role when accepted

## Rate Limiting (External Invitations)

External invitations are rate limited to prevent abuse. "External" means inviting someone who is NOT already an org member.

**Trust Model:**

| Scenario                               | Rate Limited? | Rationale               |
| -------------------------------------- | :-----------: | ----------------------- |
| Org member inviting another org member |      No       | High trust within org   |
| Inviting someone outside the org       |      Yes      | Lower trust, abuse risk |
| Inviting non-existent user (by email)  |      Yes      | Spam potential          |

**Limits:**

- **10 external invitations per hour** per user
- Applies to both project and page editor invitations
- Counter resets after 1 hour window

**Abuse Detection:**

When a user exceeds the limit:

1. Request returns `429 Too Many Requests`
2. Warning logged with user details
3. Admin notified via email immediately

**Implementation Notes:**

- Uses Django's cache framework (not Django Ninja's `@throttle` decorator)
- Reason: Need to check request body (invited email) to determine if external
- Django Ninja throttles run before body parsing, can't implement conditional logic
- See `backend/core/rate_limit.py` for implementation

**Related Files:**

- `backend/core/rate_limit.py` - Rate limit utilities
- `backend/pages/api/pages.py` - Page editor endpoint (uses rate limiting)
- `backend/pages/api/projects.py` - Project editor endpoint (uses rate limiting)

## Access Code (Read-Only Public Sharing)

Pages have an `access_code` field for unauthenticated read-only access:

- Generate: `POST /api/pages/{id}/access-code/`
- Remove: `DELETE /api/pages/{id}/access-code/`
- 43-character secure token
- Anyone with the code can view (not edit) the page
- Managed via SharePageModal

## Project Access Source

When listing projects with `details=full`, each project includes an `access_source` field:

| Value       | Meaning                                         | Pages Shown     |
| ----------- | ----------------------------------------------- | --------------- |
| `full`      | User has project-level access (Tier 0, 1, or 2) | All pages       |
| `page_only` | User only has page-level access (Tier 3)        | Accessible only |

## Key Permission Functions

Located in `backend/pages/permissions.py`:

```python
user_can_access_org(user, org)           # Is user an org member?
user_is_org_admin(user, org)             # Is user an org admin?
user_can_access_project(user, project)   # Tier 0, 1, or 2 (read access)
user_can_access_page(user, page)         # Tier 0, 1, 2, or 3 (read access)
user_can_edit_in_project(user, project)  # Write access at project level
user_can_edit_in_page(user, page)        # Write access at page level (NEW)
user_can_manage_page_sharing(user, page) # Can add/remove page editors (NEW)
user_can_modify_project(user, project)   # Same as edit_in_project
user_can_delete_project(user, project)   # Creator only
user_can_delete_page_in_project(user, page) # Creator only
get_page_access_source(user, page)       # Returns access source string
get_user_page_access_label(user, page)   # Human-readable access level (NEW)
```

## Key Manager Methods

```python
# Get all projects user can access (Tier 0, 1, 2, or 3)
Project.objects.get_user_accessible_projects(user)

# Get all pages user can access (Tier 0, 1, 2, or 3)
Page.objects.get_user_editable_pages(user)

# Get all orgs user belongs to
Org.objects.filter(members=user)
```

## Model Relationships

```
User
  ├── OrgMember (org, role) ──────────→ Org ──→ Project ──→ Page
  ├── ProjectEditor (project, role) ─────────→ Project ──→ Page
  └── PageEditor (page, role) ─────────────────────────────→ Page
```

## API Endpoints

### Page Editors

- `GET /api/pages/{id}/editors/` - List page editors
- `POST /api/pages/{id}/editors/` - Add editor (with role)
- `DELETE /api/pages/{id}/editors/{user_id}/` - Remove editor
- `PATCH /api/pages/{id}/editors/{user_id}/` - Update role

### Page Sharing Settings

- `GET /api/pages/{id}/sharing/` - Get sharing settings (your_access, access_code, can_manage_sharing)

## File Locations

```
backend/
├── pages/
│   ├── constants.py             # ProjectEditorRole, PageEditorRole enums
│   ├── permissions.py           # Permission check functions
│   ├── models/
│   │   ├── projects.py          # Project model
│   │   ├── pages.py             # Page model
│   │   ├── editors.py           # ProjectEditor, PageEditor (both with role)
│   │   └── invitations.py       # Invitation models (both with role)
│   └── api/
│       ├── projects.py          # Project endpoints (incl. role PATCH)
│       └── pages.py             # Page endpoints (incl. editors & sharing)
└── users/
    └── models/orgs.py           # Org, OrgMember models

frontend/src/lib/
├── components/
│   ├── SharePageModal.svelte    # Page sharing modal (NEW)
│   ├── ShareProjectModal.svelte # Project sharing modal
│   └── Sidenav.svelte           # Updated page context menu
├── stores/
│   └── modal.svelte.js          # Modal state management
└── modal.js                     # Modal API functions
```
