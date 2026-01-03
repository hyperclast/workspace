from datetime import timedelta

import django_rq
import markdown2
from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.views.utils import get_user_nav_context
from users.models import User

from .models import Update


def get_subscriber_count():
    thirty_days_ago = timezone.now() - timedelta(days=30)
    return User.objects.filter(
        profile__receive_product_updates=True,
        profile__last_active__gte=thirty_days_ago,
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

    from .tasks import send_test_update_email as send_test_task

    result = send_test_task(update.id, test_email, fetch_spam_score=False)

    if not result.get("success"):
        return JsonResponse({"error": result.get("error", "Failed to send")}, status=500)

    return JsonResponse(
        {
            "success": True,
            "message": f"Test email sent to {test_email}",
        }
    )


@require_POST
def check_spam_score(request, slug):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    update = get_object_or_404(Update, slug=slug)

    import markdown2
    from .tasks import check_spam_score as check_spam_task, render_update_email

    content_html = markdown2.markdown(
        update.content,
        extras={"fenced-code-blocks": {"cssclass": ""}, "tables": None},
    )
    subject, html_body, text_body = render_update_email(update, content_html)
    from_email = getattr(settings, "UPDATES_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL)

    spam_info = check_spam_task(subject, html_body, text_body, from_email)

    if not spam_info:
        return JsonResponse({"error": "Failed to check spam score"}, status=500)

    update.spam_score = spam_info.get("score")
    update.spam_rules = spam_info.get("rules")
    update.save(update_fields=["spam_score", "spam_rules"])

    return JsonResponse(
        {
            "success": True,
            "spam_score": spam_info,
        }
    )
