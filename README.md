# Aisha AI — эзотерический Telegram-бот

Персональный AI-компаньон для нумерологии, матрицы судьбы, прогнозов и совместимости.

## Стек

- Python 3.12+
- aiogram 3.13 (async Telegram framework)
- PostgreSQL 16 + SQLAlchemy 2 + asyncpg
- Redis (кэш + rate-limit + FSM storage)
- OpenAI API (gpt-4o-mini / gpt-4o)
- APScheduler (push-уведомления)
- Docker Compose

## Быстрый старт

### 1. Настройка переменных окружения

```bash
cp .env.example .env
```

Заполни `.env`:
```
BOT_TOKEN=         # токен от @BotFather
OPENAI_API_KEY=    # ключ OpenAI
DATABASE_URL=postgresql+asyncpg://numeiro:numeiro_pass@localhost:5432/numeiro
REDIS_URL=redis://localhost:6379/0
ADMIN_IDS=         # твой Telegram ID (через запятую)
```

### 2. Запуск через Docker Compose

```bash
docker-compose up -d
```

Бот, PostgreSQL и Redis запустятся автоматически. Таблицы БД создадутся сами.

### 3. Запуск без Docker (dev-режим)

```bash
pip install -r requirements.txt
python -m bot.main
```

## Структура проекта

```
bot/
├── handlers/        # обработчики Telegram
│   ├── start.py     — /start, главное меню, тарифы
│   ├── profile.py   — FSM: ввод даты рождения и пола
│   ├── reading.py   — бесплатный разбор + матрица судьбы
│   ├── weekly.py    — недельный расклад
│   ├── compatibility.py — совместимость (FSM)
│   ├── daily.py     — ежедневный прогноз
│   ├── question.py  — личный вопрос (FSM)
│   ├── dates.py     — подбор благоприятных дат
│   ├── payments.py  — Telegram Stars оплата
│   ├── admin.py     — команды администратора
│   └── share.py     — share-кнопки
├── services/
│   ├── numerology.py  — числа судьбы (только код, без AI)
│   ├── matrix.py      — матрица судьбы (только код)
│   ├── compatibility.py — совместимость (только код)
│   ├── dates.py       — подбор дат (только код)
│   ├── ai_service.py  — вызовы OpenAI + логирование токенов
│   ├── cache.py       — Redis кэш + rate-limit
│   ├── limits.py      — управление лимитами тарифов
│   └── scheduler.py   — push-уведомления
├── keyboards/main.py  — все клавиатуры
├── middlewares/
│   ├── db.py          — сессия БД
│   ├── user.py        — авторегистрация пользователя
│   └── rate_limit.py  — защита от спама
├── prompts/prompts.py — системные промпты
└── models/user.py     — все SQLAlchemy модели
```

## Тарифы

| Тариф | Цена | Срок |
|-------|------|------|
| Free  | 0    | ∞    |
| Lite  | 299 ⭐ | 7 дней |
| Premium | 999 ⭐ | 30 дней |
| Pro   | 1499 ⭐ | 30 дней |

## Разовые покупки

| Продукт | Цена |
|---------|------|
| Полная матрица судьбы | 299 ⭐ |
| Совместимость | 199 ⭐ |
| Расклад на неделю | 199 ⭐ |
| Личный вопрос | 99 ⭐ |
| Подбор дат | 199 ⭐ |

## Команды администратора

```
/stats              — статистика пользователей и дохода
/user <tg_id>       — данные конкретного пользователя
/grant <tg_id> <plan> <days>  — выдать подписку
/broadcast <текст>  — рассылка всем пользователям
/costs              — расходы на AI
/limits             — топ пользователей по лимитам
```

## AI-архитектура

Все числовые расчёты делаются кодом. AI только интерпретирует:
- `gpt-4o-mini` — короткие ответы, ежедневные прогнозы, бесплатные разборы
- `gpt-4o` — полные матрицы судьбы, глубокие разборы

Кэш (Redis) сохраняет одинаковые запросы и снижает расходы на AI.
