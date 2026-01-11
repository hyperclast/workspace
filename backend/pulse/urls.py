from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("growth/", views.growth_dashboard, name="growth"),
    path("recompute/", views.recompute, name="recompute"),
]
