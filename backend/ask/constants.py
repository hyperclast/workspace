from django.db.models import TextChoices


class AIProvider(TextChoices):
    OPENAI = "openai", "OpenAI"
    ANTHROPIC = "anthropic", "Anthropic"
    GOOGLE = "google", "Google"


class AskRequestStatus(TextChoices):
    PENDING = "pending", "Pending"
    OK = "ok", "OK"
    FAILED = "failed", "Failed"


class AskRequestError(TextChoices):
    EMPTY_QUESTION = "empty_question", "Blank or empty question"
    NO_MATCHING_PAGES = "no_matching_pages", "No matching pages"
    API_ERROR = "api_error", "API returned an error"
    UNEXPECTED = "unexpected", "Unable to process question"


def ask_request_error_map(errcode: str) -> str:
    if errcode not in AskRequestError.values:
        errcode = AskRequestError.UNEXPECTED.value
    return getattr(AskRequestError, errcode.upper()).label
