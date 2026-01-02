from datetime import timedelta

import django_rq
import markdown2
from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.views.utils import get_user_nav_context
from users.models import User

from .models import Update

UNSUBSCRIBE_TOKEN_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def get_subscriber_count():
    thirty_days_ago = timezone.now() - timedelta(days=30)
    return User.objects.filter(
        receive_product_updates=True,
        last_active__gte=thirty_days_ago,
    ).count()


def update_list(request):
    updates = Update.objects.filter(is_published=True)
    context = {
        "updates": updates,
        "brand_name": getattr(settings, "BRAND_NAME", "Hyperclast"),
        **get_user_nav_context(request),
    }
    return render(request, "updates/list.html", context)


def update_detail(request, slug):
    update = get_object_or_404(Update, slug=slug)

    if not update.is_published and not (request.user.is_authenticated and request.user.is_superuser):
        raise Http404("Update not found")

    content_html = markdown2.markdown(
        update.content,
        extras={
            "fenced-code-blocks": {"cssclass": ""},
            "tables": None,
            "header-ids": None,
        },
    )

    context = {
        "update": update,
        "content_html": content_html,
        "brand_name": getattr(settings, "BRAND_NAME", "Hyperclast"),
        "is_superuser": request.user.is_authenticated and request.user.is_superuser,
        "subscriber_count": get_subscriber_count()
        if request.user.is_authenticated and request.user.is_superuser
        else 0,
        **get_user_nav_context(request),
    }
    return render(request, "updates/detail.html", context)


@require_POST
def send_update_email(request, slug):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    update = get_object_or_404(Update, slug=slug)

    if update.emailed_at:
        return JsonResponse({"error": "Email already sent for this update"}, status=400)

    queue = django_rq.get_queue(settings.JOB_EMAIL_QUEUE)
    queue.enqueue("updates.tasks.send_update_to_subscribers", update.id)

    return JsonResponse({"success": True, "message": "Email queued for delivery"})


@require_POST
def send_test_update_email(request, slug):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    update = get_object_or_404(Update, slug=slug)

    test_email = settings.UPDATES_TEST_EMAIL
    queue = django_rq.get_queue(settings.JOB_EMAIL_QUEUE)
    queue.enqueue("updates.tasks.send_test_update_email", update.id, test_email)

    return JsonResponse({"success": True, "message": f"Test email queued for {test_email}"})


def unsubscribe(request, token):
    brand_name = getattr(settings, "BRAND_NAME", "Hyperclast")
    signer = TimestampSigner(salt="updates-unsubscribe")

    try:
        user_id = signer.unsign(token, max_age=UNSUBSCRIBE_TOKEN_MAX_AGE)
        user = User.objects.get(pk=int(user_id))

        if user.receive_product_updates:
            user.receive_product_updates = False
            user.save(update_fields=["receive_product_updates"])

        context = {
            "brand_name": brand_name,
            "success": True,
            "email": user.email,
        }
    except (BadSignature, SignatureExpired, User.DoesNotExist):
        context = {
            "brand_name": brand_name,
            "success": False,
            "error": "This unsubscribe link is invalid or has expired.",
        }

    return render(request, "updates/unsubscribe.html", context)
