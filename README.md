# Городской ассистент

## Запуск через Docker

Для запуска должны быть установлены Docker и Docker Compose.

1. Скопируйте файл с настройками:

```bash
cp .env.example .env
```

2. Откройте `.env` и укажите собственный токен GigaChat:

```env
GIGACHAT_AUTH_KEY=ваш_токен
```

3. Запустите проект:

```bash
docker compose up --build
```

После запуска интерфейс будет доступен по адресу
<http://localhost:8501>, документация API — <http://localhost:8000/docs>.
