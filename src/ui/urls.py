from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "ui"

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="ui/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.article_list, name="article_list"),
    path("articles/add/", views.article_add, name="article_add"),
    path("articles/<uuid:article_id>/", views.article_detail, name="article_detail"),
    path(
        "articles/<uuid:article_id>/delete/",
        views.article_delete,
        name="article_delete",
    ),
    path(
        "articles/<uuid:article_id>/status/",
        views.article_status,
        name="article_status",
    ),
]
