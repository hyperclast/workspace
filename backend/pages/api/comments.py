import base64
import binascii
from datetime import datetime
from typing import List, Optional

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Field, Query, Router, Schema

from backend.utils import log_warning
from collab.utils import notify_comments_updated
from core.authentication import session_auth, token_auth
from pages.models import AIPersona, Comment, Page
from pages.permissions import user_can_edit_in_page
from pages.throttling import AIReviewThrottle, CommentCreationThrottle


comments_router = Router(auth=[token_auth, session_auth])


# --- Constants ---

COMMENT_BODY_MAX_LENGTH = 10_000
COMMENT_ANCHOR_TEXT_MAX_LENGTH = 5_000
COMMENT_ANCHOR_B64_MAX_LENGTH = 500
COMMENTS_PAGE_SIZE_MAX = 100
REPLIES_PAGE_SIZE_MAX = 50
REPLIES_DEFAULT_LIMIT = 20
AI_REVIEW_DEDUP_TIMEOUT = 300  # seconds


# --- Schemas ---


class AuthorOut(Schema):
    external_id: str
    email: str
    display_name: str


class CommentsQueryParams(Schema):
    limit: int = Field(default=COMMENTS_PAGE_SIZE_MAX, le=COMMENTS_PAGE_SIZE_MAX)
    offset: int = Field(default=0, ge=0)
    replies_limit: int = Field(default=REPLIES_DEFAULT_LIMIT, le=REPLIES_PAGE_SIZE_MAX)


class RepliesQueryParams(Schema):
    limit: int = Field(default=REPLIES_DEFAULT_LIMIT, le=REPLIES_PAGE_SIZE_MAX)
    offset: int = Field(default=0, ge=0)


class CommentOut(Schema):
    external_id: str
    parent_id: Optional[str] = None
    author: Optional[AuthorOut] = None
    ai_persona: str = ""
    requester: Optional[AuthorOut] = None
    body: str
    anchor_from_b64: Optional[str] = None
    anchor_to_b64: Optional[str] = None
    anchor_text: str = ""
    created: datetime
    modified: datetime
    replies: List["CommentOut"] = []
    replies_count: int = 0


class CommentsListOut(Schema):
    items: List[CommentOut]
    count: int


class RepliesListOut(Schema):
    items: List[CommentOut]
    count: int


class CommentCreateIn(Schema):
    body: str = Field(..., max_length=COMMENT_BODY_MAX_LENGTH)
    parent_id: Optional[str] = None
    anchor_from_b64: Optional[str] = Field(None, max_length=COMMENT_ANCHOR_B64_MAX_LENGTH)
    anchor_to_b64: Optional[str] = Field(None, max_length=COMMENT_ANCHOR_B64_MAX_LENGTH)
    anchor_text: Optional[str] = Field(None, max_length=COMMENT_ANCHOR_TEXT_MAX_LENGTH)


class CommentUpdateIn(Schema):
    body: Optional[str] = Field(None, max_length=COMMENT_BODY_MAX_LENGTH)
    anchor_from_b64: Optional[str] = Field(None, max_length=COMMENT_ANCHOR_B64_MAX_LENGTH)
    anchor_to_b64: Optional[str] = Field(None, max_length=COMMENT_ANCHOR_B64_MAX_LENGTH)


class AIReviewIn(Schema):
    persona: str


class AIReviewOut(Schema):
    status: str
    message: str


# --- Helpers ---


def _get_display_name(user) -> str:
    """Derive display_name from first_name/last_name, falling back to email."""
    name = f"{user.first_name} {user.last_name}".strip()
    return name if name else user.email


def _author_out(user) -> Optional[AuthorOut]:
    if user is None:
        return None
    return AuthorOut(
        external_id=user.external_id,
        email=user.email,
        display_name=_get_display_name(user),
    )


def _comment_to_out(comment, replies=None, replies_count=0) -> CommentOut:
    anchor_from_b64 = None
    anchor_to_b64 = None
    if comment.anchor_from:
        anchor_from_b64 = base64.b64encode(bytes(comment.anchor_from)).decode("ascii")
    if comment.anchor_to:
        anchor_to_b64 = base64.b64encode(bytes(comment.anchor_to)).decode("ascii")

    return CommentOut(
        external_id=comment.external_id,
        parent_id=comment.parent.external_id if comment.parent_id else None,
        author=_author_out(comment.author),
        ai_persona=comment.ai_persona,
        requester=_author_out(comment.requester),
        body=comment.body,
        anchor_from_b64=anchor_from_b64,
        anchor_to_b64=anchor_to_b64,
        anchor_text=comment.anchor_text,
        created=comment.created,
        modified=comment.modified,
        replies=replies or [],
        replies_count=replies_count,
    )


# --- Endpoints ---


@comments_router.get("/{external_id}/comments/", response=CommentsListOut)
def list_comments(request: HttpRequest, external_id: str, query: CommentsQueryParams = Query(...)):
    """List comments for a page, with nested replies."""
    page = get_object_or_404(
        Page.objects.get_user_accessible_pages(request.user),
        external_id=external_id,
    )

    # Fetch root comments with pagination
    root_qs = (
        Comment.objects.filter(page=page, parent__isnull=True)
        .select_related("author", "requester", "parent")
        .order_by("created")
    )
    total = root_qs.count()
    roots = list(root_qs[query.offset : query.offset + query.limit])

    if not roots:
        return CommentsListOut(items=[], count=total)

    root_ids = [r.id for r in roots]
    replies_qs = (
        Comment.objects.filter(parent_id__in=root_ids)
        .select_related("author", "requester", "parent")
        .order_by("created")
    )

    replies_by_parent = {}
    for reply in replies_qs:
        replies_by_parent.setdefault(reply.parent_id, []).append(reply)

    items = []
    for root in roots:
        all_replies = replies_by_parent.get(root.id, [])
        limited = all_replies[: query.replies_limit]
        reply_outs = [_comment_to_out(r) for r in limited]
        items.append(_comment_to_out(root, replies=reply_outs, replies_count=len(all_replies)))

    return CommentsListOut(items=items, count=total)


@comments_router.get(
    "/{external_id}/comments/{comment_id}/replies/",
    response={200: RepliesListOut, 404: dict},
)
def list_replies(
    request: HttpRequest,
    external_id: str,
    comment_id: str,
    query: RepliesQueryParams = Query(...),
):
    """List replies for a root comment, with pagination."""
    page = get_object_or_404(
        Page.objects.get_user_accessible_pages(request.user),
        external_id=external_id,
    )

    root = Comment.objects.filter(page=page, external_id=comment_id, parent__isnull=True).first()
    if not root:
        return 404, {"detail": "Comment not found."}

    replies_qs = Comment.objects.filter(parent=root).select_related("author", "requester", "parent").order_by("created")
    total = replies_qs.count()
    replies = list(replies_qs[query.offset : query.offset + query.limit])
    items = [_comment_to_out(r) for r in replies]

    return RepliesListOut(items=items, count=total)


@comments_router.post(
    "/{external_id}/comments/",
    response={201: CommentOut, 400: dict, 403: dict, 404: dict, 429: dict},
    throttle=[CommentCreationThrottle()],
)
def create_comment(request: HttpRequest, external_id: str, payload: CommentCreateIn):
    """Create a comment (root or reply) on a page."""
    page = get_object_or_404(
        Page.objects.get_user_accessible_pages(request.user),
        external_id=external_id,
    )

    if not user_can_edit_in_page(request.user, page):
        return 403, {"detail": "You do not have edit access to this page."}

    # Validate: replies
    parent = None
    if payload.parent_id:
        parent = Comment.objects.filter(page=page, external_id=payload.parent_id, parent__isnull=True).first()
        if not parent:
            return 404, {"detail": "Parent comment not found."}

        # Replies must not have anchors
        if payload.anchor_from_b64 or payload.anchor_to_b64:
            return 400, {"detail": "Replies cannot have their own anchors."}
    else:
        # Root comments are either anchored (have anchor_text) or page-level (no anchor)
        pass

    if not payload.body or not payload.body.strip():
        return 400, {"detail": "Comment body cannot be empty."}

    # Decode anchors if provided
    anchor_from = None
    anchor_to = None
    try:
        if payload.anchor_from_b64:
            anchor_from = base64.b64decode(payload.anchor_from_b64)
        if payload.anchor_to_b64:
            anchor_to = base64.b64decode(payload.anchor_to_b64)
    except (binascii.Error, ValueError):
        return 400, {"detail": "Invalid base64 in anchor data."}

    comment = Comment.objects.create(
        page=page,
        author=request.user,
        parent=parent,
        anchor_from=anchor_from,
        anchor_to=anchor_to,
        anchor_text=payload.anchor_text or "",
        body=payload.body.strip(),
    )

    # Broadcast to other clients
    notify_comments_updated(str(page.external_id))

    return 201, _comment_to_out(comment)


@comments_router.post(
    "/{external_id}/comments/ai-review/",
    response={202: AIReviewOut, 400: dict, 403: dict, 404: dict, 409: dict, 429: dict},
    throttle=[AIReviewThrottle()],
)
def trigger_ai_review(request: HttpRequest, external_id: str, payload: AIReviewIn):
    """Trigger an AI persona review of a page. Comments are created asynchronously."""
    page = get_object_or_404(
        Page.objects.get_user_accessible_pages(request.user),
        external_id=external_id,
    )

    if not user_can_edit_in_page(request.user, page):
        return 403, {"detail": "You do not have edit access to this page."}

    # Validate persona
    valid_personas = [choice[0] for choice in AIPersona.choices]
    if payload.persona not in valid_personas:
        return 400, {"detail": f"Invalid persona. Must be one of: {', '.join(valid_personas)}"}

    from pages.tasks import run_ai_review

    # Atomic dedup: set a cache flag for this page+persona.
    # cache.add() is atomic — returns False if the key already exists.
    # Auto-expires after 5 minutes as a safety net if the job crashes.
    cache_key = f"ai_review:{page.id}:{payload.persona}"
    if not cache.add(cache_key, 1, timeout=AI_REVIEW_DEDUP_TIMEOUT):
        return 409, {"detail": f"{payload.persona.capitalize()} is already reviewing this page."}

    # Sync content from latest Yjs snapshot before enqueuing
    try:
        from collab.tasks import sync_snapshot_with_page

        room_id = f"page_{external_id}"
        sync_snapshot_with_page(room_id)
        page.refresh_from_db(fields=["details"])
    except Exception:
        log_warning("Failed to sync Yjs snapshot before AI review for page %s", external_id)

    # Enqueue the AI review job
    persona_name = payload.persona.capitalize()
    run_ai_review.enqueue(page.id, payload.persona, request.user.id)

    return 202, AIReviewOut(
        status="queued",
        message=f"{persona_name} is reviewing your page...",
    )


@comments_router.patch(
    "/{external_id}/comments/{comment_id}/",
    response={200: CommentOut, 400: dict, 403: dict, 404: dict},
)
def update_comment(request: HttpRequest, external_id: str, comment_id: str, payload: CommentUpdateIn):
    """Update a comment's body or set anchors (deferred resolution)."""
    page = get_object_or_404(
        Page.objects.get_user_accessible_pages(request.user),
        external_id=external_id,
    )

    if not user_can_edit_in_page(request.user, page):
        return 403, {"detail": "You do not have edit access to this page."}

    comment = Comment.objects.filter(page=page, external_id=comment_id).select_related("author").first()
    if not comment:
        return 404, {"detail": "Comment not found."}

    update_fields = []

    # Body edit — author only
    if payload.body is not None:
        if comment.author_id != request.user.id:
            return 403, {"detail": "Only the comment author can edit the body."}
        if not payload.body.strip():
            return 400, {"detail": "Comment body cannot be empty."}
        comment.body = payload.body.strip()
        update_fields.append("body")

    # Anchor setting — deferred resolution (any client can set if currently null)
    if payload.anchor_from_b64 is not None or payload.anchor_to_b64 is not None:
        # Only allow setting anchors if they're currently null (first-write-wins)
        if comment.anchor_from is not None or comment.anchor_to is not None:
            # Already anchored — no-op, return current state
            pass
        elif comment.parent_id is not None:
            return 400, {"detail": "Replies cannot have their own anchors."}
        else:
            try:
                if payload.anchor_from_b64:
                    comment.anchor_from = base64.b64decode(payload.anchor_from_b64)
                    update_fields.append("anchor_from")
                if payload.anchor_to_b64:
                    comment.anchor_to = base64.b64decode(payload.anchor_to_b64)
                    update_fields.append("anchor_to")
            except (binascii.Error, ValueError):
                return 400, {"detail": "Invalid base64 in anchor data."}

    if update_fields:
        update_fields.append("modified")
        comment.save(update_fields=update_fields)

        notify_comments_updated(str(page.external_id))

    return 200, _comment_to_out(comment)


@comments_router.delete(
    "/{external_id}/comments/{comment_id}/",
    response={204: None, 403: dict, 404: dict},
)
def delete_comment(request: HttpRequest, external_id: str, comment_id: str):
    """Delete a comment. Root comment deletion cascades to replies."""
    page = get_object_or_404(
        Page.objects.get_user_accessible_pages(request.user),
        external_id=external_id,
    )

    comment = Comment.objects.filter(page=page, external_id=comment_id).first()
    if not comment:
        return 404, {"detail": "Comment not found."}

    # AI comments: any editor can delete
    if comment.ai_persona:
        if not user_can_edit_in_page(request.user, page):
            return 403, {"detail": "You do not have edit access to this page."}
    else:
        # Human comments: author only
        if comment.author_id != request.user.id:
            return 403, {"detail": "Only the comment author can delete this comment."}

    comment.delete()

    notify_comments_updated(str(page.external_id))

    return 204, None
