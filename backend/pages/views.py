from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.html import escape

from .models import Page, PageInvitation, ProjectInvitation


def accept_invitation(request, token):
    """Handles invitation acceptance.

    Flow:
    1. Validate invitation (exists, not expired, not accepted)
    2. If user is authenticated:
       - Check email matches invitation
       - Accept invitation and redirect to page
    3. If user is NOT authenticated:
       - Store token in session
       - Redirect to signup with email pre-filled
    """
    # Get the invitation
    invitation = PageInvitation.objects.get_valid_invitation(token)

    if not invitation:
        # Invalid, expired, or already accepted invitation
        return render(
            request,
            "pages/invitation_invalid.html",
            {
                "message": "This invitation link is invalid, has expired, or has already been used.",
                "FRONTEND_URL": settings.FRONTEND_URL,
            },
        )

    # User is authenticated
    if request.user.is_authenticated:
        # Check if user's email matches the invitation email
        if request.user.email.lower() != invitation.email.lower():
            return render(
                request,
                "pages/invitation_invalid.html",
                {
                    "message": f"This invitation is for {invitation.email}. Please log out and sign in with the correct account.",
                    "FRONTEND_URL": settings.FRONTEND_URL,
                },
            )

        # Accept the invitation
        try:
            invitation.accept(request.user)
            messages.success(request, f"You now have access to '{invitation.page.title}'")

            # Redirect to the page in the frontend
            return redirect(invitation.page.page_url)

        except ValueError as e:
            # Invitation no longer valid (edge case - race condition)
            return render(
                request,
                "pages/invitation_invalid.html",
                {
                    "message": str(e),
                    "FRONTEND_URL": settings.FRONTEND_URL,
                },
            )

    # User is NOT authenticated - store token and redirect to signup
    request.session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY] = token
    request.session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY] = invitation.email

    # Redirect to signup page with next parameter (URL-encoded for safety)
    signup_url = f"/accounts/signup/?next={quote(invitation.page.page_url, safe='')}"

    return redirect(signup_url)


def accept_project_invitation(request, token):
    """Handles project invitation acceptance.

    Flow:
    1. Validate invitation (exists, not expired, not accepted)
    2. If user is authenticated:
       - Check email matches invitation
       - Accept invitation and redirect to project
    3. If user is NOT authenticated:
       - Store token in session
       - Redirect to signup with email pre-filled
    """
    # Get the invitation
    invitation = ProjectInvitation.objects.get_valid_invitation(token)

    if not invitation:
        # Invalid, expired, or already accepted invitation
        return render(
            request,
            "pages/invitation_invalid.html",
            {
                "message": "This invitation link is invalid, has expired, or has already been used.",
                "FRONTEND_URL": settings.FRONTEND_URL,
            },
        )

    # User is authenticated
    if request.user.is_authenticated:
        # Check if user's email matches the invitation email
        if request.user.email.lower() != invitation.email.lower():
            return render(
                request,
                "pages/invitation_invalid.html",
                {
                    "message": f"This invitation is for {invitation.email}. Please log out and sign in with the correct account.",
                    "FRONTEND_URL": settings.FRONTEND_URL,
                },
            )

        # Accept the invitation
        try:
            invitation.accept(request.user)
            project_name = invitation.project.name or "the project"
            messages.success(request, f"You now have access to '{project_name}'")

            # Redirect to the project in the frontend
            return redirect(invitation.project.project_url)

        except ValueError as e:
            # Invitation no longer valid (edge case - race condition)
            return render(
                request,
                "pages/invitation_invalid.html",
                {
                    "message": str(e),
                    "FRONTEND_URL": settings.FRONTEND_URL,
                },
            )

    # User is NOT authenticated - store token and redirect to signup
    request.session[settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY] = token
    request.session[settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY] = invitation.email

    # Redirect to signup page with next parameter (URL-encoded for safety)
    signup_url = f"/accounts/signup/?next={quote(invitation.project.project_url, safe='')}"

    return redirect(signup_url)


def render_markdown_simple(content):
    """Convert markdown-like content to simple HTML for read-only display.

    Only handles basic formatting - paragraphs and line breaks.
    Content is already escaped before this function is called.
    """
    if not content:
        return ""

    # Split by double newlines for paragraphs
    paragraphs = content.split("\n\n")
    html_parts = []

    for para in paragraphs:
        if para.strip():
            # Convert single newlines to <br>
            para_html = para.replace("\n", "<br>")
            html_parts.append(f"<p>{para_html}</p>")

    return "".join(html_parts)


def shared_page(request, access_code):
    """Display a read-only view of a shared page.

    This view is public (no authentication required).
    Security is provided by the unguessable 43-character access code.
    """
    # Get the page
    try:
        page = Page.objects.get(access_code=access_code, is_deleted=False)
    except Page.DoesNotExist:
        return render(
            request,
            "pages/shared_page.html",
            {
                "error": True,
                "error_message": "This page doesn't exist or is no longer shared.",
                "brand_name": settings.BRAND_NAME,
            },
            status=404,
        )

    # Get page content
    content = page.details.get("content", "") if page.details else ""

    return render(
        request,
        "pages/shared_page.html",
        {
            "page": page,
            "title": escape(page.title or "Untitled"),
            "content_html": render_markdown_simple(escape(content)),
            "updated": page.updated,
            "brand_name": settings.BRAND_NAME,
        },
    )
