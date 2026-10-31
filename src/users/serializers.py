from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username")
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    """Для ендпоинта логина юзера."""

    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(trim_whitespace=False, write_only=True)
