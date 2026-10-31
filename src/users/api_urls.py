from django.urls import path

from .views import LoginView, LogoutView, UserListView

app_name = "users_api"

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("users/", UserListView.as_view(), name="user-list"),
]
