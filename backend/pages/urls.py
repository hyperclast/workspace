from django.urls import path

from . import views


urlpatterns = [
    path("invitations/accept/<str:token>/", views.accept_invitation, name="accept_invitation"),
    path(
        "project-invitations/accept/<str:token>/",
        views.accept_project_invitation,
        name="accept_project_invitation",
    ),
]
