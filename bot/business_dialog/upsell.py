"""Система апсейлов бабушки Аиши — лестница тиров."""
import random

# ─── Тиры ─────────────────────────────────────────────────────────────────────

TIERS = {
    "t190": {
        "price":          190,
        "name":           "Первичный просмотр",
        "followup_limit": 2,
        "msg_soft_limit": None,   # без лимита сообщений
        "days":           None,
        "next_tier":      "t490",
        "link_key":       "tribute_link",  # из config.settings
    },
    "t490": {
        "price":          490,
        "name":           "Глубокий разбор причины",
        "followup_limit": 5,
        "msg_soft_limit": None,
        "days":           1,
        "next_tier":      "t990",
        "link":           "https://t.me/tribute/app?startapp=pwvQ",
    },
    "t990": {
        "price":          990,
        "name":           "Прогноз развития ситуации",
        "followup_limit": 5,
        "msg_soft_limit": None,
        "days":           3,
        "next_tier":      "t1990",
        "link":           "https://t.me/tribute/app?startapp=pwvR",
    },
    "t1990": {
        "price":          1990,
        "name":           "Личная стратегия на 7 дней",
        "followup_limit": None,   # сопровождение — нет фиксированных follow-up
        "msg_soft_limit": 40,     # soft-limit 30-50 сообщений
        "days":           7,
        "next_tier":      "t4990",
        "link":           "https://t.me/tribute/app?startapp=pwvS",
    },
    "t4990": {
        "price":          4990,
        "name":           "Сопровождение",
        "followup_limit": None,
        "msg_soft_limit": 160,    # soft-limit 120-200 сообщений
        "days":           7,
        "next_tier":      "t9900",
        "link":           "https://t.me/tribute/app?startapp=pwvT",
    },
    "t9900": {
        "price":          9900,
        "name":           "Глубокий закрытый просмотр",
        "followup_limit": None,
        "msg_soft_limit": None,   # мягкое завершение без явных лимитов
        "days":           7,
        "next_tier":      None,
        "link":           "https://t.me/tribute/app?startapp=pwvU",
    },
}

# Маппинг суммы оплаты → тир
AMOUNT_TO_TIER = {
    190:  "t190",
    490:  "t490",
    990:  "t990",
    1990: "t1990",
    4990: "t4990",
    9900: "t9900",
}

# ─── Мостики-апсейлы (текст перехода к следующему тиру) ───────────────────────

_UPSELL_BRIDGES = {
    "t490": [
        "В вашей ситуации есть скрытый слой, который я пока не показала {e}\n\nТам может быть ответ на самый важный вопрос.",
        "Первый просмотр показал поверхность {e}\n\nНо под ней — причина, которая всё объясняет.",
        "Я вижу кое-что важное, что осталось за рамками этого просмотра {e}\n\nЭто требует отдельного внимательного взгляда.",
    ],
    "t990": [
        "Причина найдена {e}\n\nНо ближайший период может всё изменить — хочу показать вам его.",
        "После того как мы нашли причину — встаёт главный вопрос {e}\n\nКак ситуация будет развиваться дальше?",
        "Теперь, когда причина ясна — важно понять что ждёт впереди {e}",
    ],
    "t1990": [
        "Прогноз показывает важный период {e}\n\nВаши действия в ближайшие дни будут особенно значимы.",
        "Ближайшие 7 дней в вашей ситуации очень важны {e}\n\nХочу провести вас через них.",
        "После прогноза хочу быть рядом — пока ситуация разворачивается {e}",
    ],
    "t4990": [
        "Ситуация живая — она продолжает меняться {e}\n\nТакие ситуации редко решаются одним просмотром.",
        "Энергии вокруг вас сейчас движутся {e}\n\nЯ чувствую, что за ней стоит наблюдать дальше.",
        "Я вижу, что процесс ещё не завершён {e}\n\nХочу наблюдать за вашей ситуацией.",
    ],
    "t9900": [
        "Ваша ситуация… особенная {e}\n\nТакой просмотр я делаю только в редких случаях.",
        "Есть вещи, которые открываются только при глубоком закрытом просмотре {e}\n\nЯ думаю, вы к этому готовы.",
        "У вас необычная ситуация {e}\n\nНекоторые вещи я могу показать только в закрытом формате.",
    ],
}


def get_tier(tier_key: str) -> dict:
    return TIERS.get(tier_key, TIERS["t190"])


def get_tier_by_amount(amount: int) -> str:
    return AMOUNT_TO_TIER.get(amount, "t190")


def tier_link(tier_key: str) -> str:
    """Tribute-ссылка для тира (t190 берёт из config)."""
    if tier_key == "t190":
        from config import settings
        return getattr(settings, "tribute_link", "")
    return TIERS.get(tier_key, {}).get("link", "")


def upsell_bridge(next_tier: str, emo: str) -> str | None:
    """Случайный мостик-апсейл для перехода к следующему тиру."""
    options = _UPSELL_BRIDGES.get(next_tier, [])
    if not options:
        return None
    return random.choice(options).format(e=emo)


def is_accompaniment(tier_key: str) -> bool:
    """Тир является сопровождением (1990+) — без разового разбора."""
    return tier_key in ("t1990", "t4990", "t9900")
