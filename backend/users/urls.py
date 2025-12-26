from django.urls import path

from . import views


urlpatterns = [
    path("stripe/cancel/", views.stripe_cancel, name="stripe_cancel"),
    path("stripe/portal/", views.stripe_portal, name="stripe_portal"),
    path("stripe/success/", views.stripe_success, name="stripe_success"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
