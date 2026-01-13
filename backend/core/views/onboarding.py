from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from backend.utils import log_error, log_info
from pages.models import Page, Project
from users.models import Org
from users.utils import compute_org_name_for_email


# Default names for new workspace
DEFAULT_PROJECT_NAME = "Demo"
DEFAULT_PAGE_TITLE = "Welcome to Hyperclast"

# Demo pages content - matches frontend demo mode
# demo_id is used to map internal links to real page IDs after creation
DEMO_PAGES = [
    {
        "demo_id": "demo-welcome",
        "title": "Welcome to Hyperclast",
        "filetype": "md",
        "content": """A fast, focused workspace for people who think in text. Try editing this page—your changes stay local until you sign up.

## Try It Out
- [ ] Click this checkbox
- [ ] Type anywhere to edit
- [x] Already done!

Use **bold**, *italic*, `inline code`, and more. Blockquotes work too:

> This is a callout. Great for notes and asides.

Code blocks with syntax highlighting:

```javascript
function greet(name) {
  return `Hello, ${name}!`;
}
```

## Explore the Demo
Check out the other pages in the sidebar:
- [Internal Links](/pages/demo-links/) — connect your ideas
- [Sections & Tasks](/pages/demo-sections/) — organize with foldable sections

## Ready to Save Your Work?
Sign up to sync across devices and collaborate with your team.
""",
    },
    {
        "demo_id": "demo-links",
        "title": "Internal Links",
        "filetype": "md",
        "content": """Build a network of connected pages with internal links.

## Creating Links
1. Select the text you want to link
2. Press **Cmd/Ctrl+K** or click the link button in the toolbar
3. Search for a page to link to

Or type `[Link Text](/pages/page-id/)` directly.

## Try These Links
- [Welcome to Hyperclast](/pages/demo-welcome/)
- [Sections & Tasks](/pages/demo-sections/)

## Backlinks
Open the **Ref** tab in the right sidebar to see which pages link here—and where this page links to.

## Autocomplete
Type `[` and the editor suggests pages. Try typing `[Welcome` to see it in action.
""",
    },
    {
        "demo_id": "demo-sections",
        "title": "Sections & Tasks",
        "filetype": "md",
        "content": """Organize long documents with foldable sections. Click the arrow in the left gutter to fold any section.

## Today
- [x] Review yesterday's notes
- [ ] Check team messages
- [ ] Plan priorities
- [ ] Update project status

## Ideas
- Feature improvements
- Bug fixes to investigate
- Documentation updates

## Meeting Notes
**Attendees:** Alice, Bob, Charlie

**Discussion:**
1. Q1 planning review
2. Resource allocation
3. Timeline updates

**Action items:**
- [ ] Follow up on budget
- [ ] Schedule next sync

## Tips
- **Fold sections** to focus on what matters
- **Checkboxes** track progress inline
- **Headers** create collapsible sections
""",
    },
    {
        "demo_id": "demo-csv",
        "title": "Sample Data",
        "filetype": "csv",
        "content": """Name,Email,Role,Status
Alice Johnson,alice@example.com,Engineer,Active
Bob Smith,bob@example.com,Designer,Active
Charlie Brown,charlie@example.com,Manager,On Leave
Diana Ross,diana@example.com,Engineer,Active
Eve Wilson,eve@example.com,Analyst,Active""",
    },
    {
        "demo_id": "demo-logs",
        "title": "Access Logs",
        "filetype": "log",
        "content": """192.168.1.1 - - [12/Jan/2026:10:15:32 +0000] "GET /api/users HTTP/2.0" 200 1234 "-" "Mozilla/5.0"
192.168.1.2 - - [12/Jan/2026:10:15:33 +0000] "POST /api/auth/login HTTP/2.0" 200 89 "-" "Mozilla/5.0"
10.0.0.5 - - [12/Jan/2026:10:15:34 +0000] "GET /static/app.js HTTP/2.0" 200 45678 "-" "Mozilla/5.0"
192.168.1.1 - - [12/Jan/2026:10:15:35 +0000] "GET /api/projects HTTP/2.0" 200 2341 "-" "Mozilla/5.0"
10.0.0.8 - - [12/Jan/2026:10:15:36 +0000] "GET /favicon.ico HTTP/2.0" 404 0 "-" "Mozilla/5.0"
192.168.1.3 - - [12/Jan/2026:10:15:37 +0000] "PUT /api/pages/abc123 HTTP/2.0" 200 567 "-" "Mozilla/5.0\"""",
    },
]


@login_required
@require_http_methods(["GET", "POST"])
def welcome(request):
    """Welcome page for new users to set up their workspace."""
    user = request.user

    # If user already has pages, redirect to their first page
    first_page = Page.objects.get_user_editable_pages(user).first()
    if first_page:
        return redirect("core:page", page_id=first_page.external_id)

    existing_org = user.orgs.first()

    # Context for display
    context = {
        "username": user.username,
        "org_name": existing_org.name if existing_org else compute_org_name_for_email(user.email),
        "project_name": DEFAULT_PROJECT_NAME,
        "page_title": DEFAULT_PAGE_TITLE,
    }

    if request.method == "GET":
        return render(request, "core/welcome.html", context)

    # POST: Create the workspace
    try:
        with transaction.atomic():
            # Get or create org
            if existing_org:
                org = existing_org
            else:
                org, _ = Org.objects.get_or_create_org_for_user(user)

            # Create project
            project = Project.objects.create(
                org=org,
                name=DEFAULT_PROJECT_NAME,
                creator=user,
            )

            # Create all demo pages and build ID mapping
            demo_id_to_real_id = {}
            created_pages = []
            for page_data in DEMO_PAGES:
                page = Page.objects.create_with_owner(
                    user=user,
                    project=project,
                    title=page_data["title"],
                    details={
                        "content": page_data["content"],
                        "filetype": page_data["filetype"],
                        "schema_version": 1,
                    },
                )
                demo_id_to_real_id[page_data["demo_id"]] = page.external_id
                created_pages.append((page, page_data))

            # Update internal links in page content to use real IDs
            for page, page_data in created_pages:
                content = page_data["content"]
                updated = False
                for demo_id, real_id in demo_id_to_real_id.items():
                    if demo_id in content:
                        content = content.replace(f"/pages/{demo_id}/", f"/pages/{real_id}/")
                        updated = True
                if updated:
                    page.details["content"] = content
                    page.save(update_fields=["details"])

            first_page = created_pages[0][0] if created_pages else None

            log_info(
                "Onboarding complete for %s: org=%s, project=%s, pages=%d",
                user.email,
                org.external_id,
                project.external_id,
                len(DEMO_PAGES),
            )

            return redirect("core:page", page_id=first_page.external_id)

    except Exception as e:
        log_error("Onboarding failed for %s: %s", user.email, e, exc_info=True)
        context["error"] = "Something went wrong. Please try again."
        return render(request, "core/welcome.html", context)
