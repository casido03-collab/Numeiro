from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    bot_token: str = Field(..., env="BOT_TOKEN")
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openrouter_api_key: str = Field(default="", env="OPENROUTER_API_KEY")
    database_url: str = Field(..., env="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    admin_ids: str = Field(default="", env="ADMIN_IDS")
    payment_provider_token: str = Field(default="", env="PAYMENT_PROVIDER_TOKEN")
    yookassa_shop_id: str = Field(default="", env="YOOKASSA_SHOP_ID")
    yookassa_secret_key: str = Field(default="", env="YOOKASSA_SECRET_KEY")
    yookassa_return_url: str = Field(default="https://t.me/numerelogia_astro_bot", env="YOOKASSA_RETURN_URL")
    tribute_link: str = Field(default="", env="TRIBUTE_LINK")
    tribute_api_key: str = Field(default="", env="TRIBUTE_API_KEY")
    vk_token: str = Field(default="", env="VK_TOKEN")
    vk_callback_confirm: str = Field(default="", env="VK_CALLBACK_CONFIRM")
    vk_callback_secret: str = Field(default="", env="VK_CALLBACK_SECRET")
    debug: bool = Field(default=False, env="DEBUG")

    @property
    def admin_ids_list(self) -> list[int]:
        if not self.admin_ids:
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

# Тарифные планы
PLANS = {
    "free": {
        "name": "Бесплатный",
        "price_stars": 0,
        "days": None,
        "limits": {
            "ai_messages": 10,         # покрывает все разовые фичи + запас
            "personal_questions": 1,   # 1 вопрос всего
            "weekly_reports": 1,
            "compatibility": 1,        # 1 совместимость всего
            "daily_forecasts": 1,      # 1 Энергия дня в день
            "mini_readings": 1,
            "date_selections": 0,
            "tarot_cards": 1,          # 1 карта Таро всего
        },
    },
    "lite": {
        "name": "Lite",
        "price_stars": 299,
        "days": 7,
        "limits": {
            "ai_messages": 120,
            "personal_questions": 7,   # 7 вопросов за подписку
            "weekly_reports": 0,
            "compatibility": 1,
            "daily_forecasts": 1,      # 1 Энергия дня в день (всего 3 за 7 дней — Redis)
            "mini_readings": 3,
            "date_selections": 2,      # 2 подбора дат
            "tarot_cards": 5,
        },
        "energy_day_total": 3,         # всего за подписку (7 дней)
    },
    "premium": {
        "name": "Premium",
        "price_stars": 999,
        "days": 30,
        "limits": {
            "ai_messages": 800,
            "personal_questions": 15,
            "weekly_reports": 2,
            "compatibility": 4,
            "daily_forecasts": 1,   # 1 Энергия дня в день, без общего лимита
            "mini_readings": 15,
            "date_selections": 10,
            "tarot_cards": 10,
        },
    },
    "pro": {
        "name": "Pro",
        "price_stars": 1499,
        "days": 30,
        "limits": {
            "ai_messages": 3000,
            "personal_questions": 60,
            "weekly_reports": 4,
            "compatibility": 15,
            "daily_forecasts": 1,   # 1 Энергия дня в день (всего 30 за месяц — Redis)
            "mini_readings": 50,
            "date_selections": 40,
            "tarot_cards": 30,
        },
        "energy_day_total": 30,     # всего за месяц (30 дней)
    },
}

# Разовые покупки (Stars)
ONE_TIME_PRODUCTS = {
    "full_matrix": {"name": "Полная матрица судьбы", "stars": 299},
    "compatibility": {"name": "Совместимость пары", "stars": 199},
    "weekly_report": {"name": "Расклад на неделю", "stars": 199},
    "personal_question": {"name": "Личный вопрос", "stars": 99},
    "date_selection": {"name": "Подбор благоприятной даты", "stars": 199},
}

# Лимиты rate-limiting
RATE_LIMITS = {
    "ai_per_10sec": 3,
    "ai_per_minute": 10,
    "compatibility_per_10min": 3,
    "buttons_per_5sec": 3,
}

# AI модели
AI_MODELS = {
    "simple": "gpt-4.1-mini",
    "medium": "gpt-4.1-mini",
    "complex": "gpt-4o",
}
