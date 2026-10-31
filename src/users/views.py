from django.contrib.auth import login, logout
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import WrongPassword, login_or_register
from .models import User
from .serializers import LoginSerializer, UserSerializer


class LoginView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer, 401: None})
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = login_or_register(**serializer.validated_data)
        except WrongPassword as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserListView(ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
