import json
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from allauth.account.models import EmailAddress
from ask.models import EmbeddingUsage, EmbeddingUsageKeySource
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from users.constants import OrgMemberRole
from users.models import AIProviderConfig, OrgMember

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

    # Get WAU data for chart
    wau_data = list(PulseMetric.objects.filter(metric_type="wau").order_by("date").values("date", "value"))
    for item in wau_data:
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
        # Use 29 days ago to match MAU's 30-day window (today - 29 days to today = 30 days)
        dau_start = today - timedelta(days=29)
        recent_dau = PulseMetric.objects.filter(
            metric_type="dau",
            date__gte=dau_start,
            date__lte=today,
        ).values_list("value", flat=True)
        if recent_dau:
            avg_dau = sum(recent_dau) / len(recent_dau)
            dau_mau_ratio = round((avg_dau / current_mau) * 100, 2)

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
            num_projects=Count("project", filter=Q(project__is_deleted=False), distinct=True),
            num_projects_deleted=Count("project", filter=Q(project__is_deleted=True), distinct=True),
            num_pages=Count(
                "created_pages",
                filter=Q(created_pages__is_deleted=False, created_pages__project__is_deleted=False),
                distinct=True,
            ),
            num_pages_deleted=Count(
                "created_pages",
                filter=(
                    Q(created_pages__is_deleted=True)
                    | Q(created_pages__project__is_deleted=True)
                    | Q(created_pages__project__isnull=True)
                ),
                distinct=True,
            ),
        )
        .order_by("-date_joined")
        .values(
            "pk",
            "email",
            "username",
            "email_verified",
            "num_projects",
            "num_projects_deleted",
            "num_pages",
            "num_pages_deleted",
            "date_joined",
            "profile__demo_visits",
        )
    )

    # Convert date_joined to string and check demo visits for template
    for user in new_users:
        user["date_joined"] = user["date_joined"].strftime("%Y-%m-%d %H:%M")
        demo_visits = user.pop("profile__demo_visits")
        user["tried_demo"] = bool(demo_visits and len(demo_visits) > 0)

    # Weekly active users: active in last 7 days but NOT new (joined before 7 days ago)
    weekly_active_users = list(
        User.objects.filter(
            profile__last_active__gte=seven_days_ago,
            date_joined__lt=seven_days_ago,
        )
        .annotate(
            email_verified=Exists(verified_email_subquery),
            num_projects=Count("project", filter=Q(project__is_deleted=False), distinct=True),
            num_projects_deleted=Count("project", filter=Q(project__is_deleted=True), distinct=True),
            num_pages=Count(
                "created_pages",
                filter=Q(created_pages__is_deleted=False, created_pages__project__is_deleted=False),
                distinct=True,
            ),
            num_pages_deleted=Count(
                "created_pages",
                filter=(
                    Q(created_pages__is_deleted=True)
                    | Q(created_pages__project__is_deleted=True)
                    | Q(created_pages__project__isnull=True)
                ),
                distinct=True,
            ),
        )
        .order_by("-profile__last_active")
        .values(
            "pk",
            "email",
            "username",
            "first_name",
            "last_name",
            "email_verified",
            "num_projects",
            "num_projects_deleted",
            "num_pages",
            "num_pages_deleted",
            "profile__last_active",
        )
    )

    for user in weekly_active_users:
        last_active = user.pop("profile__last_active")
        user["last_active"] = last_active.strftime("%Y-%m-%d %H:%M") if last_active else "Never"

    # Inactive users: active in last 90 days but NOT in last 7 days
    inactive_users = list(
        User.objects.filter(
            profile__last_active__gte=ninety_days_ago,
            profile__last_active__lt=seven_days_ago,
        )
        .annotate(
            email_verified=Exists(verified_email_subquery),
            num_projects=Count("project", filter=Q(project__is_deleted=False), distinct=True),
            num_projects_deleted=Count("project", filter=Q(project__is_deleted=True), distinct=True),
            num_pages=Count(
                "created_pages",
                filter=Q(created_pages__is_deleted=False, created_pages__project__is_deleted=False),
                distinct=True,
            ),
            num_pages_deleted=Count(
                "created_pages",
                filter=(
                    Q(created_pages__is_deleted=True)
                    | Q(created_pages__project__is_deleted=True)
                    | Q(created_pages__project__isnull=True)
                ),
                distinct=True,
            ),
        )
        .order_by("-profile__last_active")
        .values(
            "pk",
            "email",
            "username",
            "first_name",
            "last_name",
            "email_verified",
            "num_projects",
            "num_projects_deleted",
            "num_pages",
            "num_pages_deleted",
            "profile__last_active",
        )
    )

    # Convert last_active to string for template
    for user in inactive_users:
        last_active = user.pop("profile__last_active")
        user["last_active"] = last_active.strftime("%Y-%m-%d %H:%M") if last_active else "Never"

    # Active referral codes
    referrers = []
    if "referrals" in getattr(settings, "PRIVATE_FEATURES", []):
        from private.referrals.models import Referrer, ReferrerStatus, ReferralStatus, VanityCode

        qs = (
            Referrer.objects.filter(status=ReferrerStatus.ACTIVE)
            .select_related("user")
            .annotate(
                num_signups=Count("referrals"),
                num_conversions=Count("referrals", filter=models.Q(referrals__status=ReferralStatus.CONVERTED)),
            )
            .order_by("-created")
        )
        vanity_map = dict(VanityCode.objects.filter(referrer__isnull=False).values_list("referrer_id", "code"))
        for a in qs:
            referrers.append(
                {
                    "pk": a.user.pk,
                    "username": a.user.username,
                    "referral_code": a.referral_code,
                    "vanity_code": vanity_map.get(a.id),
                    "num_signups": a.num_signups,
                    "num_conversions": a.num_conversions,
                    "created": a.created.strftime("%Y-%m-%d"),
                }
            )

    # Users with AI keys (personal or via org membership)
    personal_by_user = defaultdict(list)
    for cfg in AIProviderConfig.objects.filter(user__isnull=False).order_by("user_id", "provider"):
        personal_by_user[cfg.user_id].append(cfg)

    org_keys_by_org = defaultdict(list)
    for cfg in AIProviderConfig.objects.filter(org__isnull=False).select_related("org").order_by("org_id", "provider"):
        org_keys_by_org[cfg.org_id].append(cfg)

    org_by_user = defaultdict(list)
    if org_keys_by_org:
        for user_id, org_id in OrgMember.objects.filter(org_id__in=org_keys_by_org.keys()).values_list(
            "user_id", "org_id"
        ):
            org_by_user[user_id].append(org_id)

    user_ids = set(personal_by_user.keys()) | set(org_by_user.keys())
    users_lookup = {u.pk: u for u in User.objects.filter(pk__in=user_ids).only("pk", "email", "username")}

    def _fmt(cfg, org_name=None):
        return {
            "name": cfg.get_display_name(),
            "key_hint": cfg.get_key_hint(),
            "is_enabled": cfg.is_enabled,
            "is_validated": cfg.is_validated,
            "org_name": org_name,
        }

    ai_key_users = []
    for uid in user_ids:
        u = users_lookup.get(uid)
        if not u:
            continue
        personal = [_fmt(c) for c in personal_by_user.get(uid, [])]
        org_entries = []
        for org_id in org_by_user.get(uid, []):
            for cfg in org_keys_by_org[org_id]:
                org_entries.append(_fmt(cfg, org_name=cfg.org.name))
        ai_key_users.append(
            {
                "pk": u.pk,
                "email": u.email,
                "username": u.username,
                "personal_providers": personal,
                "org_providers": org_entries,
                "total": len(personal) + len(org_entries),
            }
        )
    ai_key_users.sort(key=lambda r: (-r["total"], r["email"]))

    # Paid orgs (Pro plan billing)
    paid_orgs = []
    paid_orgs_total = 0
    paid_orgs_payment_failed = 0
    if apps.is_installed("private.billing"):
        from private.billing.models import OrgBilling, PlanChoices

        pro_billings = list(
            OrgBilling.objects.filter(plan=PlanChoices.PRO)
            .select_related("org")
            .annotate(member_count=Count("org__members", distinct=True))
            .order_by("stripe_payment_failed", "-modified")
        )
        paid_orgs_total = len(pro_billings)
        paid_orgs_payment_failed = sum(1 for b in pro_billings if b.stripe_payment_failed)

        org_ids = [b.org_id for b in pro_billings]
        members_by_org = defaultdict(list)
        for om in OrgMember.objects.filter(org_id__in=org_ids).select_related("user").order_by("-role", "created"):
            members_by_org[om.org_id].append(
                {
                    "pk": om.user.pk,
                    "email": om.user.email,
                    "username": om.user.username,
                    "is_admin": om.role == OrgMemberRole.ADMIN.value,
                }
            )

        for b in pro_billings:
            paid_orgs.append(
                {
                    "org_id": b.org_id,
                    "org_name": b.org.name or b.org.external_id,
                    "payment_failed": b.stripe_payment_failed,
                    "member_count": b.member_count,
                    "members": members_by_org.get(b.org_id, []),
                    "modified": b.modified.strftime("%Y-%m-%d") if b.modified else "",
                    "upgraded_at": b.upgraded_at.strftime("%Y-%m-%d") if b.upgraded_at else "",
                }
            )

    # Embeddings spend (Hyperclast-paid; everything routed through the server key)
    thirty_days_ago_dt = now - timedelta(days=30)
    server_usage_qs = EmbeddingUsage.objects.filter(key_source=EmbeddingUsageKeySource.SERVER)

    def _spend_rollup(qs):
        agg = qs.aggregate(cost=Sum("cost_usd"), tokens=Sum("total_tokens"), calls=Count("id"))
        return {
            "cost": agg["cost"] or Decimal("0"),
            "tokens": agg["tokens"] or 0,
            "calls": agg["calls"] or 0,
        }

    emb_lifetime = _spend_rollup(server_usage_qs)
    emb_30d = _spend_rollup(server_usage_qs.filter(created__gte=thirty_days_ago_dt))
    emb_7d = _spend_rollup(server_usage_qs.filter(created__gte=seven_days_ago))

    # User-keyed call count is informational — self-hosters paying their own OpenAI bill
    emb_user_keyed_calls_30d = EmbeddingUsage.objects.filter(
        key_source=EmbeddingUsageKeySource.USER, created__gte=thirty_days_ago_dt
    ).count()

    # Daily server spend for last 30 days
    emb_daily_raw = (
        server_usage_qs.filter(created__gte=thirty_days_ago_dt)
        .annotate(day=TruncDate("created"))
        .values("day")
        .annotate(cost=Sum("cost_usd"), calls=Count("id"))
        .order_by("day")
    )
    emb_daily_data = [
        {
            "date": row["day"].isoformat(),
            "cost": float(row["cost"] or 0),
            "calls": row["calls"] or 0,
        }
        for row in emb_daily_raw
    ]

    # Top users by lifetime server-side spend
    emb_top_users = list(
        server_usage_qs.exclude(user__isnull=True)
        .values("user_id", "user__email", "user__username")
        .annotate(
            total_cost=Sum("cost_usd"),
            total_tokens=Sum("total_tokens"),
            total_calls=Count("id"),
        )
        .order_by("-total_cost")[:20]
    )

    context = {
        "dau_data_json": json.dumps(dau_data),
        "signups_data_json": json.dumps(signups_data),
        "mau_data_json": json.dumps(mau_data),
        "wau_data_json": json.dumps(wau_data),
        "current_mau": current_mau,
        "mom_growth": mom_growth,
        "dau_mau_ratio": dau_mau_ratio,
        "last_computed": last_computed,
        "new_users": new_users,
        "weekly_active_users": weekly_active_users,
        "inactive_users": inactive_users,
        "referrers": referrers,
        "ai_key_users": ai_key_users,
        "paid_orgs": paid_orgs,
        "paid_orgs_total": paid_orgs_total,
        "paid_orgs_payment_failed": paid_orgs_payment_failed,
        "billing_enabled": apps.is_installed("private.billing"),
        "emb_lifetime": emb_lifetime,
        "emb_30d": emb_30d,
        "emb_7d": emb_7d,
        "emb_user_keyed_calls_30d": emb_user_keyed_calls_30d,
        "emb_daily_data_json": json.dumps(emb_daily_data),
        "emb_top_users": emb_top_users,
        "emb_server_key_configured": bool(getattr(settings, "EMBEDDINGS_SERVER_API_KEY", "")),
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
        # Use 29 days ago to match MAU's 30-day window (today - 29 days to today = 30 days)
        dau_start = today - timedelta(days=29)
        recent_dau = PulseMetric.objects.filter(
            metric_type="dau",
            date__gte=dau_start,
            date__lte=today,
        ).values_list("value", flat=True)
        if recent_dau:
            avg_dau = sum(recent_dau) / len(recent_dau)
            dau_mau_ratio = round((avg_dau / current_mau) * 100, 2)

    context = {
        "mau_data_json": json.dumps(mau_data),
        "current_mau": current_mau,
        "mom_growth": mom_growth,
        "dau_mau_ratio": dau_mau_ratio,
    }
    return render(request, "pulse/growth.html", context)
