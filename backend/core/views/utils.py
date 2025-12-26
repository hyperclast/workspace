import hashlib


def get_user_nav_context(request):
    """Build common context for pages that show app nav when logged in."""
    if not request.user.is_authenticated:
        return {}

    email = request.user.email or ""
    email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()

    return {
        "user_email": email,
        "user_initial": email[0].upper() if email else "?",
        "gravatar_url": f"https://www.gravatar.com/avatar/{email_hash}?s=64&d=404",
    }
