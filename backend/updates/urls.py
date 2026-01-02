from django.urls import path

from . import views

app_name = "updates"

urlpatterns = [
    path("", views.update_list, name="list"),
    path("<slug:slug>/", views.update_detail, name="detail"),
    path("<slug:slug>/send-email/", views.send_update_email, name="send_email"),
    path("<slug:slug>/send-test-email/", views.send_test_update_email, name="send_test_email"),
    path("<slug:slug>/check-spam/", views.check_spam_score, name="check_spam"),
]
