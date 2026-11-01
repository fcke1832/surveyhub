Запуск

docker compose up -d --build - сборка образа и поднять контейнеры
docker compose up -d - поднять уже собранные контейнеры
docker compose down - остановить контейнеры, данные в бд сохранятся
docker compose down -v - остановить и удалить данные из бд
docker compose ps - показать статус контейнеров
docker compose logs -f web - смотреть логи веб-сервера


http://localhost:8000 - API
http://localhost:8000/api/docs/  - swagger
http://localhost:9999 - Dozzle (логи)


Проверка

uv sync - установить зависимости
uv run pytest - прогнать тесты
uv run ruff check . --fix - проверить и поправить код линтером
uv run ruff format . - отформатировать код


Работа сервиса

Открыть в браузере http://localhost:8000/api/docs/

Нажать Authorize (сверху), выбрать basicAuth, ввести логин и пароль, нажать Authorize и Close.

POST /api/v1/auth/login/  {"username": "test user", "password": "pass"} - завести пользователя
POST /api/v1/surveys/  {"title": "Опрос 1", "description": "текст"} - создать опрос под автором
POST /api/v1/surveys/{id}/questions/ {"text": "вопрос"} - добавить вопрос
POST /api/v1/questions/{id}/options/ {"text": "Да"} - добавить вариант ответа (минимум 2 на вопрос)}
POST /api/v1/surveys/{id}/publish/ {} - опубликовать опрос

Пройти опрос надо под другим пользователем.
GET /api/v1/surveys/{id}/next-question/ - получить текущий вопрос
POST /api/v1/surveys/{id}/answers/  {"question_id": <id вопроса>, "option_id": <id ответа>} или {"question_id": <id вопроса>, "custom_text": "свой ответ"}
Повторять пару запросов, пока в ответе не появится completed: true. Вопросы даются по одному, ответить на следующий раньше времени нельзя.

GET /api/v1/surveys/{id}/stats/ - посмотреть статистику (под автором опроса)
