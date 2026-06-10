"""
Дополнительные переводы — строки которых не было в оригинальном translations_filled.py.
Подключаются через t() из translations.py после merge.
"""

EXTRA_TEXTS: dict[str, dict[str, str]] = {

    # ══════════════════════════════════════════════════════════════════
    # ДНИ НЕДЕЛИ
    # ══════════════════════════════════════════════════════════════════

    "weekday_0": {
        "ru": "Понедельник",
        "en": "Monday",
        "fa": "دوشنبه",
        "tr": "Pazartesi",
    },
    "weekday_1": {
        "ru": "Вторник",
        "en": "Tuesday",
        "fa": "سه‌شنبه",
        "tr": "Salı",
    },
    "weekday_2": {
        "ru": "Среда",
        "en": "Wednesday",
        "fa": "چهارشنبه",
        "tr": "Çarşamba",
    },
    "weekday_3": {
        "ru": "Четверг",
        "en": "Thursday",
        "fa": "پنجشنبه",
        "tr": "Perşembe",
    },
    "weekday_4": {
        "ru": "Пятница",
        "en": "Friday",
        "fa": "جمعه",
        "tr": "Cuma",
    },
    "weekday_5": {
        "ru": "Суббота",
        "en": "Saturday",
        "fa": "شنبه",
        "tr": "Cumartesi",
    },
    "weekday_6": {
        "ru": "Воскресенье",
        "en": "Sunday",
        "fa": "یکشنبه",
        "tr": "Pazar",
    },

    # ══════════════════════════════════════════════════════════════════
    # ЭНЕРГИЯ ДНЯ
    # ══════════════════════════════════════════════════════════════════

    "daily_already_used": {
        "ru": "⚡ *Энергия дня*\n\n✨ Вы уже получили энергию дня сегодня.\nВозвращайтесь завтра за новым прогнозом! 🌙",
        "en": "⚡ *Energy of the day*\n\n✨ You have already received today's energy.\nCome back tomorrow for a new forecast! 🌙",
        "fa": "⚡ *انرژی روز*\n\n✨ شما امروز انرژی روز را دریافت کرده‌اید.\nفردا برای پیش‌بینی جدید برگردید! 🌙",
        "tr": "⚡ *Günün enerjisi*\n\n✨ Bugünün enerjisini zaten aldınız.\nYeni bir tahmin için yarın gelin! 🌙",
    },
    "daily_limit_reached": {
        "ru": "⚡ *Энергия дня*\n\n🔒 Вы использовали все {max_total} прогнозов по тарифу *{plan_name}*.\n\nОбновите подписку для продолжения.",
        "en": "⚡ *Energy of the day*\n\n🔒 You have used all {max_total} forecasts on the *{plan_name}* plan.\n\nUpgrade your subscription to continue.",
        "fa": "⚡ *انرژی روز*\n\n🔒 شما همه {max_total} پیش‌بینی تعرفه *{plan_name}* را استفاده کرده‌اید.\n\nبرای ادامه اشتراک خود را ارتقا دهید.",
        "tr": "⚡ *Günün enerjisi*\n\n🔒 *{plan_name}* planındaki {max_total} tahminin tamamını kullandınız.\n\nDevam etmek için aboneliğinizi yükseltin.",
    },
    "daily_header": {
        "ru": "⚡ *Энергия дня — {name}*\n_{weekday}, {date}_\n\n",
        "en": "⚡ *Energy of the day — {name}*\n_{weekday}, {date}_\n\n",
        "fa": "⚡ *انرژی روز — {name}*\n_{weekday}، {date}_\n\n",
        "tr": "⚡ *Günün enerjisi — {name}*\n_{weekday}, {date}_\n\n",
    },

    # ══════════════════════════════════════════════════════════════════
    # ГОРОСКОП
    # ══════════════════════════════════════════════════════════════════

    "horoscope_cooldown": {
        "ru": "Следующий гороскоп откроется через *{time_left}* 🌙\n\nА пока посмотрите на энергию дня или задайте вопрос.",
        "en": "The next horoscope will be available in *{time_left}* 🌙\n\nMeanwhile, check the energy of the day or ask a question.",
        "fa": "طالع‌بینی بعدی در *{time_left}* باز می‌شود 🌙\n\nفعلاً انرژی روز را بررسی کنید یا سؤالی بپرسید.",
        "tr": "Bir sonraki burç yorumu *{time_left}* içinde açılacak 🌙\n\nBu arada günün enerjisine bakın veya bir soru sorun.",
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
        "fa": (
            "خوش آمدید، عزیزانم.\n\n"
            "اکنون می‌توانید سؤال خود را بپرسید و تفسیر شخصی وضعیت خود را دریافت کنید.\n\n"
            "🔮 *۱ سؤال رایگان باقی مانده*\n\n"
            "هرچه بیشتر توضیح دهید، عمیق‌تر می‌توانم بررسی کنم.\n\n"
            "مثلاً:\n\n"
            "_«آیا باید امسال شغلم را عوض کنم؟»_\n"
            "_«چرا همان الگو در روابطم تکرار می‌شود؟»_\n"
            "_«چه چیزی مانع پیشرفتم می‌شود؟»_\n\n"
            "✍️ *سؤال خود را بنویسید:*"
        ),
        "tr": (
            "Hoş geldiniz, canlarım.\n\n"
            "Şimdi sorunuzu sorabilir ve durumunuz hakkında kişisel bir yorum alabilirsiniz.\n\n"
            "🔮 *1 ücretsiz soru kaldı*\n\n"
            "Ne kadar ayrıntı verirseniz, o kadar derine bakabilirim.\n\n"
            "Örneğin:\n\n"
            "_«Bu yıl iş değiştirmeli miyim?»_\n"
            "_«Neden ilişkilerimde aynı örüntü tekrar ediyor?»_\n"
            "_«İlerlememi ne engelliyor?»_\n\n"
            "✍️ *Sorunuzu yazın:*"
        ),
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
        "fa": (
            "خوش آمدید، عزیزانم.\n\n"
            "سؤال خود را بپرسید — با جزئیات و صادقانه پاسخ خواهم داد.\n\n"
            "هرچه بیشتر توضیح دهید، پاسخ دقیق‌تری خواهید گرفت.\n\n"
            "✍️ *سؤال خود را بنویسید:*"
        ),
        "tr": (
            "Hoş geldiniz, canlarım.\n\n"
            "Sorunuzu sorun — ayrıntılı ve dürüstçe yanıtlayacağım.\n\n"
            "Ne kadar ayrıntı verirseniz, cevap o kadar doğru olacaktır.\n\n"
            "✍️ *Sorunuzu yazın:*"
        ),
    },

    # ══════════════════════════════════════════════════════════════════
    # ТАРИФЫ — полный текст (для иностранных пользователей)
    # ══════════════════════════════════════════════════════════════════

    "plans_full_text": {
        "ru": (
            "📜 <b>Тарифы Aisha AI</b>\n\n"
            "Ваш текущий тариф: <b>{plan}</b>\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🆓 <b>Бесплатно</b> (лимиты даются один раз)\n"
            "• 10 AI‑сообщений\n• 1 вопрос Бабушке Aisha\n• 1 Гороскоп на день\n"
            "• 1 Энергия дня (ежедневно)\n• 1 мини‑разбор\n• 1 совместимость\n• 1 Карта дня\n\n"
            "━━━━━━━━━━━━━━━\n"
            "💫 <b>Lite</b> — 299 ₽ / 7 дней\n"
            "• 120 AI‑сообщений\n• 7 вопросов\n• 1 Гороскоп\n• 1 совместимость\n"
            "• 2 подбора дат\n• 3 Энергии дня\n• 3 мини‑разбора\n• 5 Карт дня\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🌟 <b>Premium</b> — 999 ₽ / месяц\n"
            "• 800 AI‑сообщений\n• 30 вопросов\n• 2 недельных расклада\n• 7 совместимостей\n"
            "• 30 Энергий дня\n• 15 мини‑разборов\n• 10 подборов дат\n• 10 Карт дня\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🔥 <b>Pro</b> — 1 499 ₽ / месяц\n"
            "• 3 000 AI‑сообщений\n• 60 вопросов\n• 4 недельных расклада\n• 30 совместимостей\n"
            "• 30 Энергий дня\n• 50 мини‑разборов\n• 40 подборов дат\n• 30 Карт дня\n"
            "• 🌟 1 Матрица судьбы в месяц\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🌟 <b>Матрица судьбы</b> — включена в Pro или разовая покупка 299 ₽.\n\n"
            "💎 Разовые покупки доступны по кнопке ниже."
        ),
        "en": (
            "📜 <b>Aisha AI Plans</b>\n\n"
            "Your current plan: <b>{plan}</b>\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🆓 <b>Free</b> (limits given once)\n"
            "• 10 AI messages\n• 1 question to Grandma Aisha\n• 1 daily horoscope\n"
            "• 1 energy of the day (daily)\n• 1 mini reading\n• 1 compatibility\n• 1 card of the day\n\n"
            "━━━━━━━━━━━━━━━\n"
            "💫 <b>Lite</b> — 299 ⭐ / 7 days\n"
            "• 120 AI messages\n• 7 questions\n• 1 horoscope\n• 1 compatibility\n"
            "• 2 date selections\n• 3 energy of the day\n• 3 mini readings\n• 5 cards of the day\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🌟 <b>Premium</b> — 999 ⭐ / month\n"
            "• 800 AI messages\n• 30 questions\n• 2 weekly readings\n• 7 compatibility reports\n"
            "• 30 energy of the day\n• 15 mini readings\n• 10 date selections\n• 10 cards of the day\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🔥 <b>Pro</b> — 1499 ⭐ / month\n"
            "• 3,000 AI messages\n• 60 questions\n• 4 weekly readings\n• 30 compatibility reports\n"
            "• 30 energy of the day\n• 50 mini readings\n• 40 date selections\n• 30 cards of the day\n"
            "• 🌟 1 destiny matrix per month\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🌟 <b>Destiny matrix</b> — included in Pro or one-time purchase 299 ⭐.\n\n"
            "💎 One-time purchases available via the button below."
        ),
        "fa": (
            "📜 <b>تعرفه‌های Aisha AI</b>\n\n"
            "تعرفه فعلی شما: <b>{plan}</b>\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🆓 <b>رایگان</b> (محدودیت‌ها یک بار داده می‌شود)\n"
            "• ۱۰ پیام هوش مصنوعی\n• ۱ سؤال از مادربزرگ Aisha\n• ۱ طالع‌بینی روزانه\n"
            "• ۱ انرژی روز (روزانه)\n• ۱ تحلیل کوچک\n• ۱ سازگاری\n• ۱ کارت روز\n\n"
            "━━━━━━━━━━━━━━━\n"
            "💫 <b>Lite</b> — ۲۹۹ ⭐ / ۷ روز\n"
            "• ۱۲۰ پیام هوش مصنوعی\n• ۷ سؤال\n• ۱ طالع‌بینی\n• ۱ سازگاری\n"
            "• ۲ انتخاب تاریخ\n• ۳ انرژی روز\n• ۳ تحلیل کوچک\n• ۵ کارت روز\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🌟 <b>Premium</b> — ۹۹۹ ⭐ / ماه\n"
            "• ۸۰۰ پیام هوش مصنوعی\n• ۳۰ سؤال\n• ۲ پیش‌بینی هفتگی\n• ۷ سازگاری\n"
            "• ۳۰ انرژی روز\n• ۱۵ تحلیل کوچک\n• ۱۰ انتخاب تاریخ\n• ۱۰ کارت روز\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🔥 <b>Pro</b> — ۱۴۹۹ ⭐ / ماه\n"
            "• ۳٬۰۰۰ پیام هوش مصنوعی\n• ۶۰ سؤال\n• ۴ پیش‌بینی هفتگی\n• ۳۰ سازگاری\n"
            "• ۳۰ انرژی روز\n• ۵۰ تحلیل کوچک\n• ۴۰ انتخاب تاریخ\n• ۳۰ کارت روز\n"
            "• 🌟 ۱ ماتریس سرنوشت در ماه\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🌟 <b>ماتریس سرنوشت</b> — در Pro گنجانده شده یا خرید یکباره ۲۹۹ ⭐.\n\n"
            "💎 خریدهای یکباره از طریق دکمه زیر موجود است."
        ),
        "tr": (
            "📜 <b>Aisha AI Tarifeleri</b>\n\n"
            "Mevcut tarifeniz: <b>{plan}</b>\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🆓 <b>Ücretsiz</b> (limitler bir kez verilir)\n"
            "• 10 Yapay zeka mesajı\n• Büyükanne Aisha'ya 1 soru\n• 1 günlük burç yorumu\n"
            "• 1 günlük enerji (her gün)\n• 1 mini yorum\n• 1 uyumluluk\n• 1 günün kartı\n\n"
            "━━━━━━━━━━━━━━━\n"
            "💫 <b>Lite</b> — 299 ⭐ / 7 gün\n"
            "• 120 Yapay zeka mesajı\n• 7 soru\n• 1 burç yorumu\n• 1 uyumluluk\n"
            "• 2 tarih seçimi\n• 3 günlük enerji\n• 3 mini yorum\n• 5 günün kartı\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🌟 <b>Premium</b> — 999 ⭐ / ay\n"
            "• 800 Yapay zeka mesajı\n• 30 soru\n• 2 haftalık yorum\n• 7 uyumluluk raporu\n"
            "• 30 günlük enerji\n• 15 mini yorum\n• 10 tarih seçimi\n• 10 günün kartı\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🔥 <b>Pro</b> — 1499 ⭐ / ay\n"
            "• 3.000 Yapay zeka mesajı\n• 60 soru\n• 4 haftalık yorum\n• 30 uyumluluk raporu\n"
            "• 30 günlük enerji\n• 50 mini yorum\n• 40 tarih seçimi\n• 30 günün kartı\n"
            "• 🌟 Ayda 1 kader matrisi\n\n"
            "━━━━━━━━━━━━━━━\n"
            "🌟 <b>Kader matrisi</b> — Pro'ya dahildir veya 299 ⭐ tek seferlik satın alma.\n\n"
            "💎 Tek seferlik satın almalar aşağıdaki düğmeyle kullanılabilir."
        ),
    },

    # ══════════════════════════════════════════════════════════════════
    # СФЕРЫ
    # ══════════════════════════════════════════════════════════════════

    "sphere_love":        {"ru": "любовь и отношения",     "en": "love and relationships",   "fa": "عشق و روابط",           "tr": "aşk ve ilişkiler"},
    "sphere_money":       {"ru": "деньги и финансы",        "en": "money and finances",        "fa": "پول و امور مالی",        "tr": "para ve finans"},
    "sphere_work":        {"ru": "работа и карьера",        "en": "work and career",           "fa": "کار و حرفه",             "tr": "iş ve kariyer"},
    "sphere_health":      {"ru": "здоровье и энергия",      "en": "health and energy",         "fa": "سلامت و انرژی",          "tr": "sağlık ve enerji"},
    "sphere_family":      {"ru": "семья",                   "en": "family",                    "fa": "خانواده",                "tr": "aile"},
    "sphere_decision":    {"ru": "важные решения",          "en": "important decisions",       "fa": "تصمیمات مهم",            "tr": "önemli kararlar"},
    "sphere_general":     {"ru": "общий прогноз",           "en": "general forecast",          "fa": "پیش‌بینی کلی",           "tr": "genel tahmin"},
    "sphere_purpose":     {"ru": "предназначение и миссия", "en": "purpose and mission",       "fa": "هدف و مأموریت",          "tr": "amaç ve misyon"},
    "sphere_growth":      {"ru": "личностный рост",         "en": "personal growth",           "fa": "رشد شخصی",               "tr": "kişisel gelişim"},
    "sphere_partnership": {"ru": "партнёрство",             "en": "partnership",               "fa": "شراکت",                  "tr": "ortaklık"},
    "sphere_children":    {"ru": "дети и родительство",     "en": "children and parenting",    "fa": "فرزندان و فرزندپروری",   "tr": "çocuklar ve ebeveynlik"},
    "sphere_education":   {"ru": "образование",             "en": "education",                 "fa": "تحصیل",                  "tr": "eğitim"},
    "sphere_relocation":  {"ru": "переезд и путешествия",   "en": "relocation and travel",     "fa": "نقل مکان و سفر",         "tr": "taşınma ve seyahat"},
    "sphere_home":        {"ru": "жильё и дом",             "en": "home and housing",          "fa": "مسکن و خانه",            "tr": "konut ve ev"},
    "sphere_spiritual":   {"ru": "духовное развитие",       "en": "spiritual development",     "fa": "رشد معنوی",              "tr": "manevi gelişim"},
    "sphere_creativity":  {"ru": "творчество и таланты",    "en": "creativity and talents",    "fa": "خلاقیت و استعدادها",     "tr": "yaratıcılık ve yetenekler"},
    "sphere_friendship":  {"ru": "дружба и окружение",      "en": "friendship",                "fa": "دوستی و محیط اجتماعی",   "tr": "arkadaşlık ve çevre"},
    "sphere_motivation":  {"ru": "мотивация и энергия",     "en": "motivation and energy",     "fa": "انگیزه و انرژی",         "tr": "motivasyon ve enerji"},
    "sphere_inner_peace": {"ru": "внутренний мир и покой",  "en": "inner peace",               "fa": "آرامش درونی",            "tr": "iç huzur"},
    "sphere_karma":       {"ru": "карма и прошлое",         "en": "karma and the past",        "fa": "کارما و گذشته",          "tr": "karma ve geçmiş"},
    "sphere_career":      {"ru": "карьерный рост",          "en": "career growth",             "fa": "پیشرفت شغلی",            "tr": "kariyer gelişimi"},

    # ══════════════════════════════════════════════════════════════════
    # ТИПЫ СОВМЕСТИМОСТИ
    # ══════════════════════════════════════════════════════════════════

    "relation_love":       {"ru": "романтические отношения",       "en": "romantic relationship", "fa": "رابطه عاشقانه",         "tr": "romantik ilişki"},
    "relation_marriage":   {"ru": "брак",                          "en": "marriage",              "fa": "ازدواج",                "tr": "evlilik"},
    "relation_friendship": {"ru": "дружба",                        "en": "friendship",            "fa": "دوستی",                 "tr": "arkadaşlık"},
    "relation_work":       {"ru": "рабочие отношения",             "en": "work relationship",     "fa": "رابطه کاری",            "tr": "iş ilişkisi"},
    "relation_ex":         {"ru": "отношения с бывшим партнёром",  "en": "relationship with ex",  "fa": "رابطه با شریک سابق",   "tr": "eski partner ile ilişki"},
    "relation_potential":  {"ru": "потенциальный партнёр",         "en": "potential partner",     "fa": "شریک بالقوه",           "tr": "potansiyel partner"},
}
