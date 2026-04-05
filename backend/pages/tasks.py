import json
from html import escape as html_escape

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

from ask.constants import AIProvider
from ask.exceptions import AIKeyNotConfiguredError
from ask.helpers.llm import create_chat_completion, get_ai_config_for_user
from backend.utils import log_error, log_info, log_warning
from collab.utils import notify_ai_review_complete, notify_comments_updated
from core.helpers import task

from .models import (
    Comment,
    Page,
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

REVIEW_MODELS = {
    AIProvider.OPENAI.value: "gpt-5.4",
    AIProvider.ANTHROPIC.value: "claude-sonnet-4-6",
    AIProvider.GOOGLE.value: "gemini/gemini-3.1-pro",
    AIProvider.CUSTOM.value: "gpt-5.4",
}

ANCHOR_INSTRUCTION = (
    "When commenting on a passage, quote the exact text you are commenting on "
    "in the `anchor_text` field. Quote at least a full sentence — enough to be "
    "unambiguous within the document. Never quote just a single word or short phrase."
)

SELECTION_INSTRUCTION = (
    "The user has selected a specific passage for review. Focus your comments "
    "exclusively on the text between the <selection> and </selection> tags. "
    "Do not comment on any text outside the selection. Your anchor_text values "
    "must be exact quotes from within the selected passage."
)

QUALITY_INSTRUCTION = (
    "Be highly selective. Only comment on passages where you have something genuinely "
    "insightful to say. Every comment must be specific and actionable — never vague or "
    "generic. Fewer high-quality comments are always better than many mediocre ones. "
    "If the text is clear and well-written with nothing meaningful to add, return an "
    "empty JSON array `[]`."
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
    "athena": (
        "You are a strategic advisor. Read the text and identify the author's goals, then "
        "push them forward with bold, concrete suggestions. Point out where the author is "
        "being timid or vague and propose decisive action. Reference specific passages. "
        "Be direct and encouraging — like Athena counseling a hero."
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

    log_info(
        "AI review response was not valid JSON array, skipping. First 500 chars: %s",
        response_text[:500],
    )
    return []


@task(settings.JOB_INTERNAL_QUEUE)
def run_ai_review(page_id: int, page_external_id: str, persona: str, requester_id: int, selection_text: str = ""):
    """Run AI review on a page (or a selected passage). Creates Comment objects for each AI comment."""
    cache_key = f"ai_review:{page_id}:{persona}"
    page_eid = page_external_id
    try:
        page = Page.objects.get(id=page_id, is_deleted=False)
        requester = User.objects.get(id=requester_id)
    except (Page.DoesNotExist, User.DoesNotExist) as e:
        log_error("AI review: page or user not found: %s", e)
        notify_ai_review_complete(page_eid, persona, 0)
        cache.delete(cache_key)
        return

    content = page.details.get("content", "")
    if not content.strip():
        log_info("AI review: page %s has no content, skipping", page_eid)
        notify_ai_review_complete(page_eid, persona, 0)
        cache.delete(cache_key)
        return

    persona_prompt = PERSONA_PROMPTS.get(persona)
    if not persona_prompt:
        log_error("AI review: unknown persona '%s'", persona)
        notify_ai_review_complete(page_eid, persona, 0)
        cache.delete(cache_key)
        return

    # Resolve review model for the user's AI provider.
    # Only use REVIEW_MODELS as a fallback when the user hasn't configured a
    # specific model, and never for custom providers (where the hardcoded model
    # name would be sent to an unrelated API base).
    try:
        config = get_ai_config_for_user(requester)
        review_model = None
        if not config.model_name and config.provider != AIProvider.CUSTOM.value:
            review_model = REVIEW_MODELS.get(config.provider)
    except AIKeyNotConfiguredError:
        log_warning("AI review: user %s has no AI config, aborting", requester_id)
        notify_ai_review_complete(page_eid, persona, 0)
        cache.delete(cache_key)
        return

    # When the user selected text, mark it in the content for the AI.
    if selection_text:
        sel_start = content.find(selection_text)
        if sel_start != -1:
            marked = (
                content[:sel_start]
                + "<selection>"
                + selection_text
                + "</selection>"
                + content[sel_start + len(selection_text) :]
            )
            numbered_content = _build_numbered_content(marked)
        else:
            # Selection not found (doc may have been edited) — send it standalone
            numbered_content = _build_numbered_content(selection_text)
    else:
        numbered_content = _build_numbered_content(content)

    context_pages = _build_context_pages(page)

    # Build system instructions — add selection scoping when applicable
    extra_instruction = f"{SELECTION_INSTRUCTION}\n\n" if selection_text else ""

    system_message = (
        f"{persona_prompt}\n\n"
        f"{QUALITY_INSTRUCTION}\n\n"
        f"{extra_instruction}"
        f"{ANCHOR_INSTRUCTION}\n\n"
        "Respond with a JSON array of comments. Each comment has two fields:\n"
        '- "anchor_text": the exact text passage you are commenting on (quoted from the document)\n'
        '- "body": your comment (markdown)\n\n'
        "If you have no meaningful comments, return an empty JSON array `[]`.\n\n"
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
        response = create_chat_completion(messages=messages, user=requester, model=review_model, max_tokens=4096)
        response_text = response["choices"][0]["message"]["content"]
    except Exception as e:
        log_error("AI review: LLM call failed for page %s: %s", page_eid, e)
        notify_ai_review_complete(page_eid, persona, 0)
        cache.delete(cache_key)
        return

    parsed_comments = _parse_ai_response(response_text)
    if not parsed_comments:
        log_info("AI review: no comments parsed for page %s", page_eid)
        notify_ai_review_complete(page_eid, persona, 0)
        cache.delete(cache_key)
        return

    log_info("AI review: creating %d comments for page %s", len(parsed_comments), page_eid)

    for item in parsed_comments:
        Comment.objects.create(
            page=page,
            author=None,
            ai_persona=persona,
            requester=requester,
            anchor_text=item["anchor_text"],
            body=item["body"],
        )

    # Broadcast comments update + review completion
    notify_comments_updated(page_eid)
    notify_ai_review_complete(page_eid, persona, len(parsed_comments))

    # Clear the in-progress flag so the user can trigger another review
    cache.delete(cache_key)


# --- AI Edit Generation ---

EDIT_SYSTEM_PROMPT = (
    "You are an editor. Based on a review comment about a passage in a document, "
    "generate text to INSERT into the document right after the commented passage.\n\n"
    "Rules:\n"
    "- Return ONLY the text to insert — no explanations, no markdown fences, no tags.\n"
    "- The text will be inserted on a new line after the paragraph the comment refers to.\n"
    "- Match the document's writing style, tone, and formatting.\n"
    "- Be concise and actionable. Integrate suggestions naturally.\n"
    "- If the comment suggests references or links, format them clearly.\n"
    "- Do NOT repeat or rewrite existing content from the passage."
)


def _extract_context_window(content, anchor_text, context_lines=50):
    """Extract ~context_lines before/after the anchor for LLM context."""
    anchor_start = content.find(anchor_text)
    if anchor_start == -1:
        # Anchor not found — return truncated content as fallback context.
        # Matches the per-page cap used in _build_context_pages() and run_ai_reply().
        return content[:MAX_CHARS_PER_PAGE]

    anchor_line = content[:anchor_start].count("\n")
    lines = content.split("\n")
    start = max(0, anchor_line - context_lines)
    end = min(len(lines), anchor_line + context_lines + 1)
    return "\n".join(lines[start:end])


def generate_edit_from_comment(comment, page, requester):
    """Call LLM to generate insertion text from an AI comment suggestion.

    Returns the text to insert (string).
    """
    content = page.details.get("content", "")
    context = _extract_context_window(content, comment.anchor_text)

    # Build the comment thread
    thread = comment.get_thread()
    thread_text = _format_thread_for_prompt(thread)

    # Resolve model — let AIKeyNotConfiguredError propagate to the caller
    config = get_ai_config_for_user(requester)
    review_model = None
    if not config.model_name and config.provider != AIProvider.CUSTOM.value:
        review_model = REVIEW_MODELS.get(config.provider)

    user_content = (
        f'Document title: "{html_escape(page.title)}"\n\n'
        f"<passage>\n{context}\n</passage>\n\n"
        f'The comment is anchored to this text: "{comment.anchor_text}"\n\n'
        f"Review comment thread:\n\n{thread_text}"
    )

    messages = [
        {"role": "system", "content": EDIT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    response = create_chat_completion(messages=messages, user=requester, model=review_model, max_tokens=4096)
    edited = response["choices"][0]["message"]["content"].strip()

    return edited


# --- AI Reply ---

REPLY_INSTRUCTION = (
    "You are continuing a conversation in a comment thread on a document. "
    "Read the conversation so far and respond naturally in character. "
    "Be concise — aim for 1-3 sentences. "
    "Respond with your reply text only, no JSON formatting."
)


def _format_thread_for_prompt(chain):
    """Format a chain of comments as conversation for the AI prompt."""
    parts = []
    for c in chain:
        if c.ai_persona:
            speaker = c.ai_persona.capitalize()
        elif c.author:
            name = f"{c.author.first_name} {c.author.last_name}".strip()
            speaker = name if name else "User"
        else:
            speaker = "User"
        parts.append(f"**{speaker}:** {c.body}")
    return "\n\n".join(parts)


@task(settings.JOB_INTERNAL_QUEUE)
def run_ai_reply(reply_comment_id: int, persona: str, requester_id: int):
    """Generate an AI persona reply to a user's comment in a thread."""
    cache_key = f"ai_reply:{reply_comment_id}"

    try:
        user_reply = Comment.objects.select_related("page", "author").get(id=reply_comment_id)
        page = user_reply.page
        page_eid = str(page.external_id)
        requester = User.objects.get(id=requester_id)
    except (Comment.DoesNotExist, User.DoesNotExist) as e:
        log_error("AI reply: comment or user not found: %s", e)
        cache.delete(cache_key)
        return

    # Check max depth before generating a reply
    if not user_reply.can_reply:
        log_info("AI reply: max depth reached for comment %s, skipping", reply_comment_id)
        cache.delete(cache_key)
        return

    persona_prompt = PERSONA_PROMPTS.get(persona)
    if not persona_prompt:
        log_error("AI reply: unknown persona '%s'", persona)
        cache.delete(cache_key)
        return

    # Build the conversation thread (single query via root FK)
    chain = user_reply.get_ancestor_chain()
    thread_text = _format_thread_for_prompt(chain)

    # Get the anchor text from the root comment
    root_comment = chain[0]
    anchor_context = ""
    if root_comment.anchor_text:
        anchor_context = (
            f"\nThe discussion is about this passage from the document:\n" f'"{root_comment.anchor_text}"\n'
        )

    # Get page content for broader context
    content = page.details.get("content", "")
    page_context = ""
    if content.strip():
        truncated = content[:MAX_CHARS_PER_PAGE]
        page_context = f"\n\n<document>\n{truncated}\n</document>"

    # Resolve model for the user's AI provider (same logic as run_ai_review).
    try:
        config = get_ai_config_for_user(requester)
        review_model = None
        if not config.model_name and config.provider != AIProvider.CUSTOM.value:
            review_model = REVIEW_MODELS.get(config.provider)
    except AIKeyNotConfiguredError:
        log_warning("AI reply: user %s has no AI config, skipping auto-reply", requester_id)
        cache.delete(cache_key)
        return

    system_message = f"{persona_prompt}\n\n{REPLY_INSTRUCTION}"
    user_content = f"{anchor_context}\nConversation so far:\n\n{thread_text}{page_context}"

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_content},
    ]

    try:
        response = create_chat_completion(messages=messages, user=requester, model=review_model, max_tokens=1024)
        response_text = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log_error("AI reply: LLM call failed for comment %s: %s", reply_comment_id, e)
        cache.delete(cache_key)
        return

    if not response_text:
        log_info("AI reply: empty response for comment %s", reply_comment_id)
        cache.delete(cache_key)
        return

    # root is the thread's root comment
    root = user_reply.root if user_reply.root_id else user_reply

    Comment.objects.create(
        page=page,
        author=None,
        ai_persona=persona,
        requester=requester,
        parent=user_reply,
        root=root,
        depth=user_reply.depth + 1,
        body=response_text,
    )

    notify_comments_updated(page_eid)
    cache.delete(cache_key)
