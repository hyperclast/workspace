from datetime import datetime, time, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from backend.utils import log_error, log_info
from core.helpers import task

from .models import PulseMetric

User = get_user_model()


@task(settings.JOB_INTERNAL_QUEUE)
def compute_dau_metrics():
    """Compute DAU, MAU, and signups for past 90 days and store in PulseMetric."""
    try:
        today = timezone.now().date()

        for days_ago in range(90):
            date = today - timedelta(days=days_ago)
            day_start = datetime.combine(date, time.min, tzinfo=dt_timezone.utc)
            day_end = datetime.combine(date, time.max, tzinfo=dt_timezone.utc)

            # DAU: users active on this day
            dau_count = User.objects.filter(
                profile__last_active__gte=day_start,
                profile__last_active__lte=day_end,
            ).count()

            PulseMetric.objects.update_or_create(
                metric_type="dau",
                date=date,
                defaults={"value": dau_count},
            )

            # Signups: users who joined on this day
            signup_count = User.objects.filter(
                date_joined__gte=day_start,
                date_joined__lte=day_end,
            ).count()

            PulseMetric.objects.update_or_create(
                metric_type="signups",
                date=date,
                defaults={"value": signup_count},
            )

            # MAU: unique users active in the 30 days ending on this date
            mau_start = datetime.combine(date - timedelta(days=29), time.min, tzinfo=dt_timezone.utc)
            mau_count = User.objects.filter(
                profile__last_active__gte=mau_start,
                profile__last_active__lte=day_end,
            ).count()

            PulseMetric.objects.update_or_create(
                metric_type="mau",
                date=date,
                defaults={"value": mau_count},
            )

        log_info("Computed pulse metrics (DAU + MAU + signups) for 90 days")

    except Exception as e:
        log_error("Error computing pulse metrics: %s", e)
        raise
