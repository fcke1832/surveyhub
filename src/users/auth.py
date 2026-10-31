from loguru import logger

from .models import User


class WrongPassword(ValueError):
    """Используется когда username есть, а пароль не совпадает"""


def login_or_register(*, username: str, password: str) -> User:
    """Возвращает юзера, если он есть в БД, или создает нового, если нет такого username"""
    logger.info(f">>>>>>>>>>>>> Trying to login as {username=}.")
    user, created = User.objects.get_or_create(username=username)
    logger.info(f">>>>>>>>>>>>> login_or_register {user=} / {created=}.")

    if created:
        user.set_password(password)
        user.save()
    elif not user.check_password(password) or not user.is_active:
        raise WrongPassword("Неверный пароль.")

    return user
