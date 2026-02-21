from http import HTTPStatus

from django.conf import settings
from ninja import Router
from ninja.responses import Response

from ask.constants import AskRequestError, ask_request_error_map
from ask.models import AskRequest
from ask.schemas import AskIn, AskOut
from ask.throttling import AskRateThrottle
from core.authentication import session_auth, token_auth

router = Router(auth=[token_auth, session_auth])


@router.post("/", response={200: AskOut, 400: dict}, throttle=[AskRateThrottle()])
def ask(request, payload: AskIn):
    """Process a user query and return an AI-generated answer.

    Calls AskRequest.objects.process_query() to handle the RAG pipeline.
    Returns the answer if successful, or an error if processing fails.
    """
    if not settings.ASK_FEATURE_ENABLED:
        return Response(
            {"error": "ask_feature_disabled", "message": "This feature is not available at this time."},
            status=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    user = request.user

    ask_request = AskRequest.objects.process_query(
        query=payload.query,
        user=user,
        page_ids=payload.page_ids,
        provider=payload.provider,
        config_id=payload.config_id,
        model=payload.model,
    )

    if not ask_request.is_ok:
        errcode = getattr(ask_request, "error", "") or AskRequestError.UNEXPECTED.value

        if errcode == "ai_key_not_configured":
            return Response(
                {
                    "error": "ai_key_not_configured",
                    "message": "No AI provider configured. Please add an API key in Settings.",
                },
                status=HTTPStatus.BAD_REQUEST,
            )

        errmsg = ask_request_error_map(errcode)
        return Response(
            {"error": errcode, "message": errmsg},
            status=HTTPStatus.BAD_REQUEST,
        )

    return 200, ask_request.results
