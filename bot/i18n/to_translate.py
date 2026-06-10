"""
ФАЙЛ ДЛЯ ПЕРЕВОДА — отдать ChatGPT.

ПРОМПТ ДЛЯ CHATGPT:
════════════════════════════════════════════════════════
Ты профессиональный переводчик. Переведи значения в словарях ниже на фарси (fa) и турецкий (tr).

Правила:
- "ru" и "en" НЕ трогать — они уже готовы
- Заполни только поля "fa" и "tr" вместо "[TODO]"
- Сохрани все эмодзи и знаки препинания
- Сохрани все {плейсхолдеры} в фигурных скобках без изменений
- Плейсхолдеры: {name}, {plan}, {max_total}, {plan_name}, {time_left}
- Стиль: тёплый, мистический, женский (бот — женщина-астролог)
- Для фарси используй правостороннее написание (RTL) — это нормально
- В турецком используй правильные символы: ş, ğ, ü, ö, ç, ı
════════════════════════════════════════════════════════
"""

EXTRA_TEXTS: dict[str, dict[str, str]] = {

    # ══════════════════════════════════════════════════════════════════
    # ДНИ НЕДЕЛИ
    # ══════════════════════════════════════════════════════════════════

    "weekday_0": {
        "ru": "Понедельник",
        "en": "Monday",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },
    "weekday_1": {
        "ru": "Вторник",
        "en": "Tuesday",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },
    "weekday_2": {
        "ru": "Среда",
        "en": "Wednesday",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },
    "weekday_3": {
        "ru": "Четверг",
        "en": "Thursday",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },
    "weekday_4": {
        "ru": "Пятница",
        "en": "Friday",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },
    "weekday_5": {
        "ru": "Суббота",
        "en": "Saturday",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },
    "weekday_6": {
        "ru": "Воскресенье",
        "en": "Sunday",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },

    # ══════════════════════════════════════════════════════════════════
    # ЭНЕРГИЯ ДНЯ
    # ══════════════════════════════════════════════════════════════════

    "daily_already_used": {
        "ru": "⚡ *Энергия дня*\n\n✨ Вы уже получили энергию дня сегодня.\nВозвращайтесь завтра за новым прогнозом! 🌙",
        "en": "⚡ *Energy of the day*\n\n✨ You have already received today's energy.\nCome back tomorrow for a new forecast! 🌙",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },
    "daily_limit_reached": {
        "ru": "⚡ *Энергия дня*\n\n🔒 Вы использовали все {max_total} прогнозов по тарифу *{plan_name}*.\n\nОбновите подписку для продолжения.",
        "en": "⚡ *Energy of the day*\n\n🔒 You have used all {max_total} forecasts on the *{plan_name}* plan.\n\nUpgrade your subscription to continue.",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },
    "daily_header": {
        "ru": "⚡ *Энергия дня — {name}*\n_{weekday}, {date}_\n\n",
        "en": "⚡ *Energy of the day — {name}*\n_{weekday}, {date}_\n\n",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },

    # ══════════════════════════════════════════════════════════════════
    # ГОРОСКОП
    # ══════════════════════════════════════════════════════════════════

    "horoscope_cooldown": {
        "ru": "Следующий гороскоп откроется через *{time_left}* 🌙\n\nА пока посмотрите на энергию дня или задайте вопрос.",
        "en": "The next horoscope will be available in *{time_left}* 🌙\n\nMeanwhile, check the energy of the day or ask a question.",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },

    # ══════════════════════════════════════════════════════════════════
    # ЛИЧНЫЙ ВОПРОС — приветствие
    # ══════════════════════════════════════════════════════════════════

    "question_welcome_free": {
        "ru": (
            "Добро пожаловать, мои хорошие.\n\n"
            "Сейчас Вы можете задать мне свой вопрос и получить индивидуальный разбор ситуации.\n\n"
            "🔮 *Остался 1 бесплатный вопрос*\n\n"
            "Чем подробнее Вы опишете ситуацию, тем глубже я смогу её рассмотреть.\n\n"
            "Например:\n\n"
            "_«Стоит ли мне менять работу в этом году?»_\n"
            "_«Почему в моих отношениях постоянно повторяется один сценарий?»_\n"
            "_«Что мешает мне двигаться вперёд?»_\n\n"
            "✍️ *Напишите свой вопрос:*"
        ),
        "en": (
            "Welcome, dear ones.\n\n"
            "You can now ask me your question and receive a personal reading of your situation.\n\n"
            "🔮 *1 free question remaining*\n\n"
            "The more detail you provide, the deeper I can look into it.\n\n"
            "For example:\n\n"
            "_«Should I change jobs this year?»_\n"
            "_«Why does the same pattern keep repeating in my relationships?»_\n"
            "_«What is holding me back?»_\n\n"
            "✍️ *Write your question:*"
        ),
        "fa": "[TODO]",
        "tr": "[TODO]",
    },
    "question_welcome_paid": {
        "ru": (
            "Добро пожаловать, мои хорошие.\n\n"
            "Задайте ваш вопрос — я отвечу развёрнуто и честно.\n\n"
            "Чем подробнее Вы опишете ситуацию, тем точнее будет ответ.\n\n"
            "✍️ *Напишите свой вопрос:*"
        ),
        "en": (
            "Welcome, dear ones.\n\n"
            "Ask your question — I will answer in detail and honestly.\n\n"
            "The more detail you provide, the more accurate the answer will be.\n\n"
            "✍️ *Write your question:*"
        ),
        "fa": "[TODO]",
        "tr": "[TODO]",
    },

    # ══════════════════════════════════════════════════════════════════
    # ТАРИФЫ — полный текст (HTML)
    # ══════════════════════════════════════════════════════════════════

    "plans_full_text_ru": {
        "ru": """📜 <b>Тарифы Aisha AI</b>

Ваш текущий тариф: <b>{plan}</b>

━━━━━━━━━━━━━━━
🆓 <b>Бесплатно</b> (лимиты даются один раз)
• 10 AI‑сообщений
• 1 вопрос Бабушке Aisha
• 1 Гороскоп на день
• 1 Энергия дня (ежедневно)
• 1 мини‑разбор
• 1 совместимость
• 1 Карта дня

━━━━━━━━━━━━━━━
💫 <b>Lite</b> — 299 ₽ / 7 дней
• 120 AI‑сообщений
• 7 вопросов Бабушке Aisha
• 1 Гороскоп на день
• 1 совместимость
• 2 подбора благоприятных дат
• 3 Энергии дня
• 3 мини‑разбора
• 5 Карт дня

━━━━━━━━━━━━━━━
🌟 <b>Premium</b> — 999 ₽ / месяц
• 800 AI‑сообщений
• 30 вопросов Бабушке Aisha
• 1 Гороскоп на день
• 2 недельных расклада
• 7 совместимостей
• 30 Энергий дня
• 15 мини‑разборов
• 10 подборов благоприятных дат
• 10 Карт дня

━━━━━━━━━━━━━━━
🔥 <b>Pro</b> — 1 499 ₽ / месяц
• 3 000 AI‑сообщений
• 60 вопросов Бабушке Aisha
• 1 Гороскоп на день
• 4 недельных расклада
• 30 совместимостей
• 30 Энергий дня
• 50 мини‑разборов
• 40 подборов благоприятных дат
• 30 Карт дня
• 🌟 1 Матрица судьбы в месяц

━━━━━━━━━━━━━━━
🌟 <b>Матрица судьбы</b> — включена в Pro или разовая покупка 299 ₽ для Lite/Premium.

💎 Разовые покупки доступны по кнопке ниже.""",
        "en": """📜 <b>Aisha AI Plans</b>

Your current plan: <b>{plan}</b>

━━━━━━━━━━━━━━━
🆓 <b>Free</b> (limits given once)
• 10 AI messages
• 1 question to Grandma Aisha
• 1 daily horoscope
• 1 energy of the day (daily)
• 1 mini reading
• 1 compatibility
• 1 card of the day

━━━━━━━━━━━━━━━
💫 <b>Lite</b> — 299 ⭐ / 7 days
• 120 AI messages
• 7 questions to Grandma Aisha
• 1 daily horoscope
• 1 compatibility
• 2 date selections
• 3 energy of the day
• 3 mini readings
• 5 cards of the day

━━━━━━━━━━━━━━━
🌟 <b>Premium</b> — 999 ⭐ / month
• 800 AI messages
• 30 questions to Grandma Aisha
• 1 daily horoscope
• 2 weekly readings
• 7 compatibility reports
• 30 energy of the day
• 15 mini readings
• 10 date selections
• 10 cards of the day

━━━━━━━━━━━━━━━
🔥 <b>Pro</b> — 1499 ⭐ / month
• 3,000 AI messages
• 60 questions to Grandma Aisha
• 1 daily horoscope
• 4 weekly readings
• 30 compatibility reports
• 30 energy of the day
• 50 mini readings
• 40 date selections
• 30 cards of the day
• 🌟 1 destiny matrix per month

━━━━━━━━━━━━━━━
🌟 <b>Destiny matrix</b> — included in Pro or one-time purchase 299 ⭐ for Lite/Premium.

💎 One-time purchases available via the button below.""",
        "fa": "[TODO]",
        "tr": "[TODO]",
    },

    # ══════════════════════════════════════════════════════════════════
    # СФЕРЫ (для AI-контекста и заголовков отчётов)
    # ══════════════════════════════════════════════════════════════════

    "sphere_love":        {"ru": "любовь и отношения",      "en": "love and relationships",      "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_money":       {"ru": "деньги и финансы",         "en": "money and finances",          "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_work":        {"ru": "работа и карьера",         "en": "work and career",             "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_health":      {"ru": "здоровье и энергия",       "en": "health and energy",           "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_family":      {"ru": "семья",                    "en": "family",                      "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_decision":    {"ru": "важные решения",           "en": "important decisions",         "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_general":     {"ru": "общий прогноз",            "en": "general forecast",            "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_purpose":     {"ru": "предназначение и миссия",  "en": "purpose and mission",         "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_growth":      {"ru": "личностный рост",          "en": "personal growth",             "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_partnership": {"ru": "партнёрство",              "en": "partnership",                 "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_children":    {"ru": "дети и родительство",      "en": "children and parenting",      "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_education":   {"ru": "образование",              "en": "education",                   "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_relocation":  {"ru": "переезд и путешествия",    "en": "relocation and travel",       "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_home":        {"ru": "жильё и дом",              "en": "home and housing",            "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_spiritual":   {"ru": "духовное развитие",        "en": "spiritual development",       "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_creativity":  {"ru": "творчество и таланты",     "en": "creativity and talents",      "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_friendship":  {"ru": "дружба и окружение",       "en": "friendship",                  "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_motivation":  {"ru": "мотивация и энергия",      "en": "motivation and energy",       "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_inner_peace": {"ru": "внутренний мир и покой",   "en": "inner peace",                 "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_karma":       {"ru": "карма и прошлое",          "en": "karma and the past",          "fa": "[TODO]", "tr": "[TODO]"},
    "sphere_career":      {"ru": "карьерный рост",           "en": "career growth",               "fa": "[TODO]", "tr": "[TODO]"},

    # ══════════════════════════════════════════════════════════════════
    # ТИПЫ СОВМЕСТИМОСТИ
    # ══════════════════════════════════════════════════════════════════

    "relation_love":      {"ru": "романтические отношения",          "en": "romantic relationship",  "fa": "[TODO]", "tr": "[TODO]"},
    "relation_marriage":  {"ru": "брак",                             "en": "marriage",               "fa": "[TODO]", "tr": "[TODO]"},
    "relation_friendship":{"ru": "дружба",                           "en": "friendship",             "fa": "[TODO]", "tr": "[TODO]"},
    "relation_work":      {"ru": "рабочие отношения",                "en": "work relationship",      "fa": "[TODO]", "tr": "[TODO]"},
    "relation_ex":        {"ru": "отношения с бывшим партнёром",     "en": "relationship with ex",   "fa": "[TODO]", "tr": "[TODO]"},
    "relation_potential": {"ru": "потенциальный партнёр",            "en": "potential partner",      "fa": "[TODO]", "tr": "[TODO]"},
}
