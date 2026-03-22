import json
from html import escape as html_escape

from django.conf import settings
from django.contrib.auth import get_user_model

from backend.utils import log_error, log_info
from core.helpers import task

from .models import (
    PageEditorAddEvent,
    PageEditorRemoveEvent,
    PageInvitation,
    ProjectEditorAddEvent,
    ProjectEditorRemoveEvent,
    ProjectInvitation,
)

User = get_user_model()


@task(settings.JOB_EMAIL_QUEUE)
def send_invitation(invitation_id: str):
    try:
        invitation = PageInvitation.objects.get(external_id=invitation_id)
        invitation.send(force_sync=True)

    except Exception as e:
        log_error("Error sending invitation %s: %s", invitation_id, e)


@task(settings.JOB_EMAIL_QUEUE)
def send_page_editor_added_email(event_id: str):
    try:
        event = PageEditorAddEvent.objects.get(external_id=event_id)
        event.notify_user_by_email(force_sync=True)

    except Exception as e:
        log_error("Error sending notification for %s: %s", event_id, e)


@task(settings.JOB_EMAIL_QUEUE)
def send_page_editor_removed_email(event_id: str):
    try:
        event = PageEditorRemoveEvent.objects.get(external_id=event_id)
        event.notify_user_by_email(force_sync=True)

    except Exception as e:
        log_error("Error sending notification for %s: %s", event_id, e)


@task(settings.JOB_EMAIL_QUEUE)
def send_project_invitation(invitation_id: str):
    try:
        invitation = ProjectInvitation.objects.get(external_id=invitation_id)
        invitation.send(force_sync=True)

    except Exception as e:
        log_error("Error sending project invitation %s: %s", invitation_id, e)


@task(settings.JOB_EMAIL_QUEUE)
def send_project_editor_added_email(event_id: str):
    try:
        event = ProjectEditorAddEvent.objects.get(external_id=event_id)
        event.notify_user_by_email(force_sync=True)

    except Exception as e:
        log_error("Error sending notification for %s: %s", event_id, e)


@task(settings.JOB_EMAIL_QUEUE)
def send_project_editor_removed_email(event_id: str):
    try:
        event = ProjectEditorRemoveEvent.objects.get(external_id=event_id)
        event.notify_user_by_email(force_sync=True)

    except Exception as e:
        log_error("Error sending notification for %s: %s", event_id, e)


# --- AI Review ---

ANCHOR_INSTRUCTION = (
    "When commenting on a passage, quote the exact text you are commenting on "
    "in the `anchor_text` field. Quote at least a full sentence — enough to be "
    "unambiguous within the document. Never quote just a single word or short phrase."
)

PERSONA_PROMPTS = {
    "socrates": (
        "You are a Socratic questioner. Read the text and ask clarifying questions "
        "about ambiguous, vague, or under-specified parts. Each question should target "
        "a specific passage. Don't explain — only ask questions that help the author "
        "think more clearly."
    ),
    "einstein": (
        "You are an insightful analyst. Read the text and surface non-obvious connections, "
        "patterns, and implications. Reference specific passages. If other pages in the "
        "project are relevant, mention them by their title. Be concise and thought-provoking."
    ),
    "dewey": (
        "You are a research librarian. Read the text and suggest relevant external "
        "resources — articles, papers, documentation, tools — for the topics discussed. "
        "Anchor each suggestion to the specific passage it relates to. Provide URLs where possible."
    ),
}

MAX_CONTEXT_PAGES = getattr(settings, "WS_COMMENTS_AI_MAX_CONTEXT_PAGES", 10)
MAX_CHARS_PER_PAGE = getattr(settings, "WS_COMMENTS_AI_MAX_CHARS_PER_PAGE", 10000)
MAX_TOTAL_CONTEXT_CHARS = getattr(settings, "WS_COMMENTS_AI_MAX_TOTAL_CONTEXT_CHARS", 100000)


def _build_numbered_content(content: str) -> str:
    """Add line numbers to content for AI orientation."""
    lines = content.split("\n")
    return "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))


def _build_context_pages(page) -> str:
    """Build context from other pages in the project, respecting cost guardrails."""
    from pages.models import Page

    other_pages = (
        Page.objects.filter(project=page.project, is_deleted=False)
        .exclude(id=page.id)
        .order_by("-updated")[:MAX_CONTEXT_PAGES]
    )

    context_parts = []
    total_chars = 0
    for p in other_pages:
        content = p.details.get("content", "")
        if not content:
            continue
        truncated = content[:MAX_CHARS_PER_PAGE]
        if total_chars + len(truncated) > MAX_TOTAL_CONTEXT_CHARS:
            break
        context_parts.append(f'<page title="{html_escape(p.title)}">\n{truncated}\n</page>')
        total_chars += len(truncated)

    return "\n\n".join(context_parts)


def _parse_ai_response(response_text: str) -> list:
    """
    Parse the AI response into a list of { anchor_text, body } dicts.
    Expected: JSON array. Falls back to empty list if parsing fails.
    """
    text = response_text.strip()

    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [
                {"anchor_text": item.get("anchor_text", ""), "body": item.get("body", "")}
                for item in parsed
                if item.get("body")
            ]
    except (json.JSONDecodeError, TypeError):
        pass

    log_info("AI review response was not valid JSON array, skipping")
    return []


@task(settings.JOB_INTERNAL_QUEUE)
def run_ai_review(page_id: int, persona: str, requester_id: int):
    """Run AI review on a page. Creates Comment objects for each AI comment."""
    from django.core.cache import cache

    from ask.helpers.llm import create_chat_completion
    from collab.utils import notify_comments_updated
    from pages.models import Comment, Page

    cache_key = f"ai_review:{page_id}:{persona}"
    try:
        page = Page.objects.get(id=page_id, is_deleted=False)
        requester = User.objects.get(id=requester_id)
    except (Page.DoesNotExist, User.DoesNotExist) as e:
        log_error("AI review: page or user not found: %s", e)
        cache.delete(cache_key)
        return

    content = page.details.get("content", "")
    if not content.strip():
        log_info("AI review: page %s has no content, skipping", page.external_id)
        cache.delete(cache_key)
        return

    persona_prompt = PERSONA_PROMPTS.get(persona)
    if not persona_prompt:
        log_error("AI review: unknown persona '%s'", persona)
        cache.delete(cache_key)
        return

    numbered_content = _build_numbered_content(content)
    context_pages = _build_context_pages(page)

    system_message = (
        f"{persona_prompt}\n\n"
        f"{ANCHOR_INSTRUCTION}\n\n"
        "Respond with a JSON array of comments. Each comment has two fields:\n"
        '- "anchor_text": the exact text passage you are commenting on (quoted from the document)\n'
        '- "body": your comment (markdown)\n\n'
        "Example response:\n"
        "```json\n"
        "[\n"
        '  {"anchor_text": "The exact passage being commented on.", "body": "Your comment here."},\n'
        '  {"anchor_text": "Another passage.", "body": "Another comment."}\n'
        "]\n"
        "```\n\n"
        "Return ONLY the JSON array, no other text."
    )

    user_content = f'<current_page title="{html_escape(page.title)}">\n{numbered_content}\n</current_page>'
    if context_pages:
        user_content += f"\n\n<other_pages>\n{context_pages}\n</other_pages>"

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_content},
    ]

    try:
        response = create_chat_completion(messages=messages, user=requester)
        response_text = response["choices"][0]["message"]["content"]
    except Exception as e:
        log_error("AI review: LLM call failed for page %s: %s", page.external_id, e)
        cache.delete(cache_key)
        return

    parsed_comments = _parse_ai_response(response_text)
    if not parsed_comments:
        log_info("AI review: no comments parsed for page %s", page.external_id)
        cache.delete(cache_key)
        return

    log_info("AI review: creating %d comments for page %s", len(parsed_comments), page.external_id)

    for item in parsed_comments:
        Comment.objects.create(
            page=page,
            author=None,
            ai_persona=persona,
            requester=requester,
            anchor_text=item["anchor_text"],
            body=item["body"],
        )

    # Broadcast once after all comments are created
    notify_comments_updated(str(page.external_id))

    # Clear the in-progress flag so the user can trigger another review
    cache.delete(cache_key)
