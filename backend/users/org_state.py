"""Centralized writes to `Profile.org_state`.

`Profile.org_state` is a JSON column keyed by org `external_id`. Every
update is a read-modify-write on the whole column, so concurrent writes
from different code paths (e.g. the user navigates to a new page in
Org A while a background daily-note PATCH for Org B settles) can lose
each other without row-level locking.

This module is the only place that mutates `Profile.org_state`. Every
write takes a `Profile` row-lock via `select_for_update()` inside an
`atomic()` block, then merges the requested keys into the bucket for
the target org and saves. Read paths can hit `user.profile.org_state`
directly; the lock matters only for writers.
"""

from django.db import transaction

from users.models import Profile


def write_bucket(user, org, **fields):
    """Merge `fields` into `Profile.org_state[org.external_id]` under a
    Profile row-lock.

    A value of `None` is written as-is (it clears that key on read).
    Keys not present in `fields` are left untouched. Returns the
    resulting bucket dict.

    The bucket shape today is::

        {
          "last_page_id":          "<page external_id>" | None,
          "daily_note_project_id": "<project external_id>" | None,
          "daily_note_template_id":"<page external_id>" | None,
        }

    but is intentionally open — adding a new per-org key only requires
    a new call-site, no schema change.
    """
    if not fields:
        return _read_bucket(user, org)

    with transaction.atomic():
        profile = Profile.objects.select_for_update().get(user=user)
        org_state = dict(profile.org_state or {})
        bucket = dict(org_state.get(org.external_id, {}))
        changed = False
        for key, value in fields.items():
            if bucket.get(key) != value:
                bucket[key] = value
                changed = True
        if not changed:
            return bucket
        org_state[org.external_id] = bucket
        profile.org_state = org_state
        profile.save(update_fields=["org_state", "modified"])
        return bucket


def read_bucket(user, org):
    """Read the org-state bucket for `org` (a fresh dict if unset).

    Returns a shallow copy so callers can't accidentally mutate the
    underlying JSON. Read path is unlocked — concurrent writes win on
    their own row-lock.
    """
    return _read_bucket(user, org)


def _read_bucket(user, org):
    bucket = (user.profile.org_state or {}).get(org.external_id, {})
    return dict(bucket) if isinstance(bucket, dict) else {}
