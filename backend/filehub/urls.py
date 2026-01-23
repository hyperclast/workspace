from django.urls import path

from filehub.views import download_by_token

urlpatterns = [
    path(
        "<str:project_id>/<str:file_id>/<str:access_token>/",
        download_by_token,
        name="download_by_token",
    ),
]
