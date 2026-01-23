from datetime import timedelta

from django.http import Http404, HttpRequest, HttpResponseRedirect

from filehub.models import FileUpload
from filehub.services.downloads import get_best_blob
from filehub.storage import get_storage_backend


def download_by_token(
    request: HttpRequest,
    project_id: str,
    file_id: str,
    access_token: str,
) -> HttpResponseRedirect:
    """
    Download a file using an access token.

    This is a public endpoint - the access token IS the authorization.
    Redirects to a short-lived signed storage URL.
    """
    try:
        file_upload = FileUpload.objects.select_related("project").get(
            deleted__isnull=True,
            project__external_id=project_id,
            external_id=file_id,
            access_token=access_token,
        )
    except FileUpload.DoesNotExist:
        raise Http404("File not found")

    if not file_upload.is_available:
        raise Http404("File not available")

    blob = get_best_blob(file_upload)
    if not blob:
        raise Http404("No blob available")

    storage = get_storage_backend(blob.provider)

    # Generate short-lived signed URL for actual download (5 min)
    download_url = storage.generate_download_url(
        bucket=blob.bucket,
        object_key=blob.object_key,
        expires_in=timedelta(minutes=5),
        filename=file_upload.filename,
    )

    return HttpResponseRedirect(download_url)
