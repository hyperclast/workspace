import json
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Exists, OuterRef
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import PulseMetric
from .tasks import compute_dau_metrics

User = get_user_model()


@login_required
def dashboard(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Admin access required")

    now = timezone.now()
    today = now.date()
    seven_days_ago = now - timedelta(days=7)
    ninety_days_ago = now - timedelta(days=90)
    thirty_days_ago = today - timedelta(days=30)

    # Get DAU data for chart (past 90 days, ordered by date ascending)
    dau_data = list(PulseMetric.objects.filter(metric_type="dau").order_by("date").values("date", "value"))
    for item in dau_data:
        item["date"] = item["date"].isoformat()

    # Get signups data for chart
    signups_data = list(PulseMetric.objects.filter(metric_type="signups").order_by("date").values("date", "value"))
    for item in signups_data:
        item["date"] = item["date"].isoformat()

    # Get MAU data for chart
    mau_data = list(PulseMetric.objects.filter(metric_type="mau").order_by("date").values("date", "value"))
    for item in mau_data:
        item["date"] = item["date"].isoformat()

    # Calculate MoM MAU Growth %
    current_mau = PulseMetric.objects.filter(metric_type="mau", date=today).values_list("value", flat=True).first()
    previous_mau = (
        PulseMetric.objects.filter(metric_type="mau", date=thirty_days_ago).values_list("value", flat=True).first()
    )

    mom_growth = None
    if current_mau is not None and previous_mau is not None and previous_mau > 0:
        mom_growth = round(((current_mau - previous_mau) / previous_mau) * 100, 1)

    # Calculate DAU/MAU ratio (average DAU over last 30 days / current MAU)
    dau_mau_ratio = None
    if current_mau and current_mau > 0:
        recent_dau = PulseMetric.objects.filter(
            metric_type="dau",
            date__gte=thirty_days_ago,
            date__lte=today,
        ).values_list("value", flat=True)
        if recent_dau:
            avg_dau = sum(recent_dau) / len(recent_dau)
            dau_mau_ratio = round((avg_dau / current_mau) * 100, 1)

    # Get last computed time
    last_computed = (
        PulseMetric.objects.filter(metric_type="dau")
        .order_by("-computed_at")
        .values_list("computed_at", flat=True)
        .first()
    )

    # New users in last 7 days with project/page counts and email verification status
    verified_email_subquery = EmailAddress.objects.filter(user=OuterRef("pk"), verified=True)

    new_users = list(
        User.objects.filter(date_joined__gte=seven_days_ago)
        .annotate(
            email_verified=Exists(verified_email_subquery),
            num_projects=Count("project", distinct=True),
            num_pages=Count("created_pages", distinct=True),
        )
        .order_by("-date_joined")
        .values(
            "email",
            "username",
            "email_verified",
            "num_projects",
            "num_pages",
            "date_joined",
            "profile__demo_visits",
        )
    )

    # Convert date_joined to string and check demo visits for template
    for user in new_users:
        user["date_joined"] = user["date_joined"].strftime("%Y-%m-%d %H:%M")
        demo_visits = user.pop("profile__demo_visits")
        user["tried_demo"] = bool(demo_visits and len(demo_visits) > 0)

    # Inactive users: active in last 90 days but NOT in last 7 days
    inactive_users = list(
        User.objects.filter(
            profile__last_active__gte=ninety_days_ago,
            profile__last_active__lt=seven_days_ago,
        )
        .annotate(
            email_verified=Exists(verified_email_subquery),
            num_projects=Count("project", distinct=True),
            num_pages=Count("created_pages", distinct=True),
        )
        .order_by("-profile__last_active")
        .values(
            "email",
            "username",
            "first_name",
            "last_name",
            "email_verified",
            "num_projects",
            "num_pages",
            "profile__last_active",
        )
    )

    # Convert last_active to string for template
    for user in inactive_users:
        last_active = user.pop("profile__last_active")
        user["last_active"] = last_active.strftime("%Y-%m-%d %H:%M") if last_active else "Never"

    context = {
        "dau_data_json": json.dumps(dau_data),
        "signups_data_json": json.dumps(signups_data),
        "mau_data_json": json.dumps(mau_data),
        "current_mau": current_mau,
        "mom_growth": mom_growth,
        "dau_mau_ratio": dau_mau_ratio,
        "last_computed": last_computed,
        "new_users": new_users,
        "inactive_users": inactive_users,
    }
    return render(request, "pulse/dashboard.html", context)


@login_required
@require_POST
def recompute(request):
    if not request.user.is_superuser:
        return JsonResponse({"error": "Forbidden"}, status=403)

    compute_dau_metrics.enqueue()
    return JsonResponse({"status": "queued"})


@login_required
def growth_dashboard(request):
    """Investor-safe dashboard showing only growth metrics (no user data)."""
    if not request.user.is_superuser:
        return HttpResponseForbidden("Admin access required")

    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)

    # Get MAU data for chart
    mau_data = list(PulseMetric.objects.filter(metric_type="mau").order_by("date").values("date", "value"))
    for item in mau_data:
        item["date"] = item["date"].isoformat()

    # Calculate MoM MAU Growth %
    current_mau = PulseMetric.objects.filter(metric_type="mau", date=today).values_list("value", flat=True).first()
    previous_mau = (
        PulseMetric.objects.filter(metric_type="mau", date=thirty_days_ago).values_list("value", flat=True).first()
    )

    mom_growth = None
    if current_mau is not None and previous_mau is not None and previous_mau > 0:
        mom_growth = round(((current_mau - previous_mau) / previous_mau) * 100, 1)

    # Calculate DAU/MAU ratio (average DAU over last 30 days / current MAU)
    dau_mau_ratio = None
    if current_mau and current_mau > 0:
        recent_dau = PulseMetric.objects.filter(
            metric_type="dau",
            date__gte=thirty_days_ago,
            date__lte=today,
        ).values_list("value", flat=True)
        if recent_dau:
            avg_dau = sum(recent_dau) / len(recent_dau)
            dau_mau_ratio = round((avg_dau / current_mau) * 100, 1)

    context = {
        "mau_data_json": json.dumps(mau_data),
        "current_mau": current_mau,
        "mom_growth": mom_growth,
        "dau_mau_ratio": dau_mau_ratio,
    }
    return render(request, "pulse/growth.html", context)
