"""
Файл переводов Aisha AI.
Языки: ru (русский), en (английский), fa (фарси/персидский), tr (турецкий)

Структура: TEXTS[ключ][язык] = строка
Плейсхолдеры: {name}, {plan}, {price}, {period}, {stars}, {date} — НЕ переводить, оставлять как есть.
"""

TEXTS: dict[str, dict[str, str]] = {

    # ══════════════════════════════════════════════════════════════════
    # ВЫБОР ЯЗЫКА (первый экран при /start)
    # ══════════════════════════════════════════════════════════════════

    "lang_select_text": {
        "ru": "🌍 Выберите язык / Choose your language:",
        "en": "🌍 Choose your language:",
        "fa": "🌍 زبان خود را انتخاب کنید / Choose your language:",
        "tr": "🌍 Dilinizi seçin / Choose your language:",
    },
    "lang_btn_ru": {
        "ru": "🇷🇺 Русский",
        "en": "🇷🇺 Русский",
        "fa": "🇷🇺 Русский",
        "tr": "🇷🇺 Русский",
    },
    "lang_btn_en": {
        "ru": "🇬🇧 English",
        "en": "🇬🇧 English",
        "fa": "🇬🇧 English",
        "tr": "🇬🇧 English",
    },
    "lang_btn_fa": {
        "ru": "🇮🇷 فارسی",
        "en": "🇮🇷 فارسی",
        "fa": "🇮🇷 فارسی",
        "tr": "🇮🇷 فارسی",
    },
    "lang_btn_tr": {
        "ru": "🇹🇷 Türkçe",
        "en": "🇹🇷 Türkçe",
        "fa": "🇹🇷 Türkçe",
        "tr": "🇹🇷 Türkçe",
    },

    # ══════════════════════════════════════════════════════════════════
    # ОНБОРДИНГ — экран 1 (приветствие)
    # ══════════════════════════════════════════════════════════════════

    "ob_screen1": {
        "ru": (
            "✨ *Иногда жизнь приводит нас сюда не случайно.*\n\n"
            "Многие замечают повторяющиеся числа, странные совпадения и внутреннее чувство,\n"
            "будто впереди что-то меняется.\n\n"
            "Возможно, именно сейчас для вас начинается новый этап."
        ),
        "en": (
            "✨ *Sometimes life brings us here for a reason.*\n\n"
            "Many people notice repeating numbers, strange coincidences and an inner feeling\n"
            "that something is about to change.\n\n"
            "Perhaps a new chapter is beginning for you right now."
        ),
        "fa": "✨ *گاهی زندگی بی‌دلیل ما را به اینجا نمی‌آورد.*\n\nخیلی‌ها اعداد تکراری، اتفاق‌های عجیب و یک حس درونی را تجربه می‌کنند؛\nانگار چیزی در مسیر پیش رو در حال تغییر است.\n\nشاید درست همین حالا، فصل تازه‌ای برای شما آغاز می‌شود.",
        "tr": "✨ *Bazen hayat bizi buraya sebepsiz getirmez.*\n\nBirçok insan tekrar eden sayıları, tuhaf tesadüfleri ve içinden gelen o hissi fark eder;\nsanki ileride bir şeyler değişmek üzeredir.\n\nBelki de tam şu anda sizin için yeni bir dönem başlıyordur.",
    },
    "ob_btn_continue": {
        "ru": "✨ Продолжить",
        "en": "✨ Continue",
        "fa": "✨ ادامه",
        "tr": "✨ Devam et",
    },

    # ══════════════════════════════════════════════════════════════════
    # ОНБОРДИНГ — экран 2 (дата рождения)
    # ══════════════════════════════════════════════════════════════════

    "ob_screen2": {
        "ru": (
            "📅 *Для персонального разбора мне нужна ваша дата рождения.*\n\n"
            "Напишите её в формате: *ДД.ММ.ГГГГ*\n\n"
            "_Например: 15.03.1990_"
        ),
        "en": (
            "📅 *For your personal reading, I need your date of birth.*\n\n"
            "Enter it in format: *DD.MM.YYYY*\n\n"
            "_Example: 15.03.1990_"
        ),
        "fa": "📅 *برای تحلیل شخصی، به تاریخ تولد شما نیاز دارم.*\n\nآن را با این فرمت بنویسید: *DD.MM.YYYY*\n\n_مثلاً: 15.03.1990_",
        "tr": "📅 *Kişisel yorumunuz için doğum tarihinize ihtiyacım var.*\n\nŞu formatta yazın: *GG.AA.YYYY*\n\n_Örneğin: 15.03.1990_",
    },
    "ob_date_invalid": {
        "ru": "❌ Не могу распознать дату. Введите в формате *ДД.ММ.ГГГГ*\n\nНапример: *15.03.1990*",
        "en": "❌ Cannot recognise the date. Enter in format *DD.MM.YYYY*\n\nExample: *15.03.1990*",
        "fa": "❌ نمی‌توانم تاریخ را تشخیص بدهم. لطفاً با فرمت *DD.MM.YYYY* وارد کنید\n\nمثلاً: *15.03.1990*",
        "tr": "❌ Tarihi anlayamadım. Lütfen *GG.AA.YYYY* formatında girin\n\nÖrneğin: *15.03.1990*",
    },
    "ob_date_invalid_range": {
        "ru": "❌ Некорректная дата. Проверьте и введите снова.",
        "en": "❌ Invalid date. Please check and try again.",
        "fa": "❌ تاریخ نامعتبر است. لطفاً بررسی کنید و دوباره وارد کنید.",
        "tr": "❌ Geçersiz tarih. Lütfen kontrol edip tekrar deneyin.",
    },

    # ══════════════════════════════════════════════════════════════════
    # ОНБОРДИНГ — экран 3 (что объединяет бот)
    # ══════════════════════════════════════════════════════════════════

    "ob_screen3_intro": {
        "ru": (
            "🔮 *Этот бот объединяет:*\n\n"
            "• нумерологию\n"
            "• совместимость\n"
            "• энергетические прогнозы\n"
            "• расклады\n"
            "• личные вопросы\n\n"
            "Чтобы помочь вам лучше понять:\n"
            "себя, отношения и происходящие события.\n\n"
            "_Что привело вас сюда?_"
        ),
        "en": (
            "🔮 *This bot combines:*\n\n"
            "• numerology\n"
            "• compatibility\n"
            "• energy forecasts\n"
            "• readings\n"
            "• personal questions\n\n"
            "To help you better understand:\n"
            "yourself, your relationships and current events.\n\n"
            "_What brought you here?_"
        ),
        "fa": "🔮 *این بات این موارد را با هم ترکیب می‌کند:*\n\n• عددشناسی\n• سازگاری\n• پیش‌بینی‌های انرژی\n• فال‌ها و چیدمان‌ها\n• پرسش‌های شخصی\n\nتا به شما کمک کند بهتر بفهمید:\nخودتان، روابطتان و اتفاق‌هایی که در جریان است.\n\n_چه چیزی شما را به اینجا آورد؟_",
        "tr": "🔮 *Bu bot şunları bir araya getirir:*\n\n• numeroloji\n• uyumluluk\n• enerji tahminleri\n• açılımlar\n• kişisel sorular\n\nKendinizi, ilişkilerinizi ve yaşanan olayları\ndaha iyi anlamanıza yardımcı olmak için.\n\n_Sizi buraya ne getirdi?_",
    },
    "ob_btn_love": {
        "ru": "❤️ Отношения",
        "en": "❤️ Relationships",
        "fa": "❤️ روابط",
        "tr": "❤️ İlişkiler",
    },
    "ob_btn_forecast": {
        "ru": "🌙 Прогнозы",
        "en": "🌙 Forecasts",
        "fa": "🌙 پیش‌بینی‌ها",
        "tr": "🌙 Tahminler",
    },
    "ob_btn_self": {
        "ru": "🔮 Самопознание",
        "en": "🔮 Self-discovery",
        "fa": "🔮 خودشناسی",
        "tr": "🔮 Kendini keşif",
    },

    # ══════════════════════════════════════════════════════════════════
    # ОНБОРДИНГ — экран 3 (тексты по теме) — минимальный EN/FA/TR
    # ══════════════════════════════════════════════════════════════════

    "ob_screen3_love": {
        "ru": (
            "❤️ *Многие люди приходят сюда именно из-за отношений.*\n\n"
            "Иногда между людьми возникает необъяснимая связь.\n"
            "А иногда судьба словно специально сталкивает нас с определёнными людьми.\n\n"
            "✨ Возможно, некоторые ответы уже ждут вас."
        ),
        "en": (
            "❤️ *Many people come here because of relationships.*\n\n"
            "Sometimes an inexplicable connection arises between people.\n"
            "And sometimes fate seems to bring us together with certain people on purpose.\n\n"
            "✨ Perhaps some answers are already waiting for you."
        ),
        "fa": "❤️ *بسیاری از مردم به خاطر روابط به اینجا می‌آیند.*\n\nگاهی پیوندی توضیح‌ناپذیر بین دو نفر ایجاد می‌شود.\n\n✨ شاید برخی پاسخ‌ها از قبل منتظر شما هستند.",
        "tr": "❤️ *Birçok insan ilişkiler nedeniyle buraya geliyor.*\n\nBazen insanlar arasında açıklanamaz bir bağ oluşur.\n\n✨ Belki bazı cevaplar sizi zaten bekliyor.",
    },
    "ob_screen3_forecast": {
        "ru": (
            "🌙 *Некоторые периоды ощущаются особенно странно.*\n\n"
            "Иногда энергия словно меняется:\n"
            "меняется настроение, мысли и даже люди вокруг.\n\n"
            "Многие замечают это ещё до важных событий."
        ),
        "en": (
            "🌙 *Some periods feel particularly unusual.*\n\n"
            "Sometimes the energy seems to shift:\n"
            "mood, thoughts, and even the people around you change.\n\n"
            "Many notice this before important events."
        ),
        "fa": "🌙 *بعضی دوره‌ها احساس خاصی دارند.*\n\nگاهی انگار انرژی عوض می‌شود:\nخلق، افکار و حتی آدم‌های اطرافت تغییر می‌کنند.\n\nبسیاری این را قبل از اتفاقات مهم احساس می‌کنند.",
        "tr": "🌙 *Bazı dönemler özellikle tuhaf hissettiriyor.*\n\nBazen enerji sanki değişiyor:\nruh hali, düşünceler ve çevrenizdeki insanlar bile değişiyor.\n\nBirçoğu bunu önemli olaylardan önce fark ediyor.",
    },
    "ob_screen3_self": {
        "ru": (
            "🔮 *Иногда человеку достаточно одного ответа,*\n"
            "чтобы посмотреть на свою жизнь под другим углом.\n\n"
            "Нумерология и энергетические практики помогают лучше понять:\n"
            "• свои сильные стороны\n"
            "• внутренние циклы\n"
            "• повторяющиеся события"
        ),
        "en": (
            "🔮 *Sometimes one answer is enough*\n"
            "to see your life from a different angle.\n\n"
            "Numerology and energy practices help you better understand:\n"
            "• your strengths\n"
            "• inner cycles\n"
            "• repeating events"
        ),
        "fa": "🔮 *گاهی یک پاسخ کافی است*\nتا زندگی را از زاویه‌ای دیگر ببینی.\n\nعددشناسی و تمرینات انرژی کمک می‌کنند بهتر بفهمی:\n• نقاط قوتت\n• چرخه‌های درونی\n• اتفاقات تکرارشونده",
        "tr": "🔮 *Bazen tek bir cevap yeterli olur*\nhayata farklı bir açıdan bakabilmek için.\n\nNumeroloji ve enerji pratikleri daha iyi anlamanıza yardımcı olur:\n• güçlü yönlerinizi\n• iç döngülerinizi\n• tekrar eden olayları",
    },
    "ob_btn_learn_more": {
        "ru": "✨ Узнать больше",
        "en": "✨ Learn more",
        "fa": "✨ بیشتر بدان",
        "tr": "✨ Daha fazla öğren",
    },

    # ══════════════════════════════════════════════════════════════════
    # ОНБОРДИНГ — экран 4 (тема интереса → анимация)
    # ══════════════════════════════════════════════════════════════════

    "ob_screen4": {
        "ru": (
            "✨ *Перед тем как открыть доступ к функциям,*\n"
            "выберите что вас интересует сейчас больше всего:"
        ),
        "en": (
            "✨ *Before opening the features,*\n"
            "choose what interests you most right now:"
        ),
        "fa": "✨ *قبل از باز شدن امکانات،*\nانتخاب کنید الان بیشتر چه چیزی برایتان مهم است:",
        "tr": "✨ *Özellikleri açmadan önce,*\nşu anda sizi en çok neyin ilgilendirdiğini seçin:",
    },
    "ob_btn_money": {
        "ru": "💰 Деньги",
        "en": "💰 Money",
        "fa": "💰 پول",
        "tr": "💰 Para",
    },
    "ob_btn_future": {
        "ru": "🌙 Будущее",
        "en": "🌙 Future",
        "fa": "🌙 آینده",
        "tr": "🌙 Gelecek",
    },
    "ob_anim_1": {
        "ru": "✨ Анализирую вашу энергетику...",
        "en": "✨ Analysing your energy...",
        "fa": "✨ دارم انرژی شما را بررسی می‌کنم...",
        "tr": "✨ Enerjinizi analiz ediyorum...",
    },
    "ob_anim_2": {
        "ru": "🌙 Считываю энергетические линии...",
        "en": "🌙 Reading energy lines...",
        "fa": "🌙 دارم خطوط انرژی را می‌خوانم...",
        "tr": "🌙 Enerji çizgilerini okuyorum...",
    },
    "ob_anim_3": {
        "ru": "🔮 Формирую персональное пространство...",
        "en": "🔮 Building your personal space...",
        "fa": "🔮 دارم فضای شخصی شما را می‌سازم...",
        "tr": "🔮 Kişisel alanınızı oluşturuyorum...",
    },
    "ob_btn_open_menu": {
        "ru": "◀️ Открыть меню",
        "en": "◀️ Open menu",
        "fa": "◀️ باز کردن منو",
        "tr": "◀️ Menüyü aç",
    },

    # ══════════════════════════════════════════════════════════════════
    # ГЛАВНОЕ МЕНЮ — кнопки
    # ══════════════════════════════════════════════════════════════════

    "menu_horoscope": {
        "ru": "🔯 Гороскоп",
        "en": "🔯 Horoscope",
        "fa": "🔯 طالع‌بینی",
        "tr": "🔯 Burç yorumu",
    },
    "menu_tarot": {
        "ru": "🃏 Карта дня",
        "en": "🃏 Card of the day",
        "fa": "🃏 کارت روز",
        "tr": "🃏 Günün kartı",
    },
    "menu_daily": {
        "ru": "⚡ Энергия дня",
        "en": "⚡ Energy of the day",
        "fa": "⚡ انرژی روز",
        "tr": "⚡ Günün enerjisi",
    },
    "menu_reading": {
        "ru": "✨ Мой разбор",
        "en": "✨ My reading",
        "fa": "✨ تحلیل من",
        "tr": "✨ Yorumum",
    },
    "menu_matrix": {
        "ru": "🌟 Полная матрица судьбы",
        "en": "🌟 Full destiny matrix",
        "fa": "🌟 ماتریس سرنوشت",
        "tr": "🌟 Kader matrisi",
    },
    "menu_weekly": {
        "ru": "📅 Расклад на неделю",
        "en": "📅 Weekly reading",
        "fa": "📅 فال هفتگی",
        "tr": "📅 Haftalık açılım",
    },
    "menu_compatibility": {
        "ru": "💞 Совместимость",
        "en": "💞 Compatibility",
        "fa": "💞 سازگاری",
        "tr": "💞 Uyumluluk",
    },
    "menu_question": {
        "ru": "🔮 Задать вопрос Бабушке Aisha",
        "en": "🔮 Ask Grandma Aisha a question",
        "fa": "🔮 سؤال از مادربزرگ Aisha",
        "tr": "🔮 Büyükanne Aisha'ya sor",
    },
    "menu_dates": {
        "ru": "📆 Подбор дат",
        "en": "📆 Date selection",
        "fa": "📆 انتخاب تاریخ",
        "tr": "📆 Tarih seçimi",
    },
    "menu_reviews": {
        "ru": "⭐ Отзывы",
        "en": "⭐ Reviews",
        "fa": "⭐ نظرها",
        "tr": "⭐ Yorumlar",
    },
    "menu_plans": {
        "ru": "📜 Тарифы",
        "en": "📜 Plans",
        "fa": "📜 تعرفه‌ها",
        "tr": "📜 Tarifeler",
    },
    "menu_history": {
        "ru": "🌀 История",
        "en": "🌀 History",
        "fa": "🌀 تاریخچه",
        "tr": "🌀 Geçmiş",
    },
    "btn_back": {
        "ru": "◀️ Назад",
        "en": "◀️ Back",
        "fa": "◀️ بازگشت",
        "tr": "◀️ Geri",
    },
    "btn_back_to_main": {
        "ru": "◀️ Главное меню",
        "en": "◀️ Main menu",
        "fa": "◀️ منوی اصلی",
        "tr": "◀️ Ana menü",
    },
    "btn_back_to_plans": {
        "ru": "◀️ К тарифам",
        "en": "◀️ Back to plans",
        "fa": "◀️ بازگشت به تعرفه‌ها",
        "tr": "◀️ Tarifelere dön",
    },

    # ══════════════════════════════════════════════════════════════════
    # ПРИВЕТСТВИЕ (/start)
    # ══════════════════════════════════════════════════════════════════

    "welcome": {
        "ru": (
            "✨ Добро пожаловать в *Aisha AI* — Компаньон собранный по многолетним наработкам Бабушки Аиши\n\n"
            "Здесь вас ждёт:\n\n"
            "🔯 *Гороскоп* — ежедневный знак зодиака и послание звёзд\n"
            "⚡️ *Энергия дня* — ежедневный бесплатный прогноз\n"
            "✨ *Мой разбор* — нумерологический анализ по дате рождения\n"
            "🌟 *Матрица судьбы* — глубокий разбор арканов и энергий\n"
            "📅 *Прогноз на неделю* — по любой сфере жизни\n"
            "💞 *Совместимость* — числа двух людей\n"
            "🔮 *Вопрос Тарологу* — личный вопрос Бабушке Aisha\n\n"
            "_Выберите, с чего начать:_"
        ),
        "en": (
            "✨ Welcome to *Aisha AI* — your companion built on years of practice by Grandma Aisha\n\n"
            "What's waiting for you:\n\n"
            "🔯 *Horoscope* — daily zodiac sign and message from the stars\n"
            "⚡️ *Energy of the day* — free daily forecast\n"
            "✨ *My reading* — numerological analysis by date of birth\n"
            "🌟 *Destiny matrix* — deep reading of arcana and energies\n"
            "📅 *Weekly forecast* — for any area of life\n"
            "💞 *Compatibility* — numbers of two people\n"
            "🔮 *Ask a question* — personal question to Grandma Aisha\n\n"
            "_Choose where to start:_"
        ),
        "fa": "✨ به *Aisha AI* خوش آمدید — همراهی که بر پایه سال‌ها تجربه و دانسته‌های مادربزرگ Aisha ساخته شده است\n\nاینجا منتظر شماست:\n\n🔯 *طالع‌بینی* — نشانه روزانه زودیاک و پیام ستاره‌ها\n⚡️ *انرژی روز* — پیش‌بینی روزانه رایگان\n✨ *تحلیل من* — تحلیل عددشناسی بر اساس تاریخ تولد\n🌟 *ماتریس سرنوشت* — بررسی عمیق آرکان‌ها و انرژی‌ها\n📅 *پیش‌بینی هفتگی* — برای هر بخش از زندگی\n💞 *سازگاری* — اعداد دو نفر\n🔮 *پرسش از تارولوگ* — سؤال شخصی از مادربزرگ Aisha\n\n_انتخاب کنید از کجا شروع کنیم:_",
        "tr": "✨ *Aisha AI*'ya hoş geldiniz — Büyükanne Aisha'nın yıllara dayanan birikimiyle hazırlanmış yol arkadaşınız\n\nBurada sizi şunlar bekliyor:\n\n🔯 *Burç yorumu* — günlük burç işareti ve yıldızlardan mesaj\n⚡️ *Günün enerjisi* — ücretsiz günlük tahmin\n✨ *Yorumum* — doğum tarihine göre numerolojik analiz\n🌟 *Kader matrisi* — arkanlar ve enerjiler üzerine derin yorum\n📅 *Haftalık tahmin* — hayatın her alanı için\n💞 *Uyumluluk* — iki kişinin sayıları\n🔮 *Taroloğa soru* — Büyükanne Aisha'ya kişisel soru\n\n_Nereden başlamak istersiniz?_",
    },

    # ══════════════════════════════════════════════════════════════════
    # ТАРИФЫ — кнопки и тексты
    # ══════════════════════════════════════════════════════════════════

    "plans_title": {
        "ru": "📜 *Тарифы Aisha AI*",
        "en": "📜 *Aisha AI Plans*",
        "fa": "📜 *تعرفه‌های Aisha AI*",
        "tr": "📜 *Aisha AI Tarifeleri*",
    },
    "plan_current": {
        "ru": "Ваш текущий тариф: *{plan}*",
        "en": "Your current plan: *{plan}*",
        "fa": "تعرفه فعلی شما: *{plan}*",
        "tr": "Mevcut tarifeniz: *{plan}*",
    },
    "plan_free_name": {
        "ru": "Бесплатный",
        "en": "Free",
        "fa": "رایگان",
        "tr": "Ücretsiz",
    },
    "plan_btn_lite": {
        "ru": "💫 Lite — 299 ₽ / 7 дней",
        "en": "💫 Lite — 299 ⭐ / 7 days",
        "fa": "💫 Lite — 299 ⭐ / 7 روز",
        "tr": "💫 Lite — 299 ⭐ / 7 gün",
    },
    "plan_btn_premium": {
        "ru": "🌟 Premium — 999 ₽ / месяц",
        "en": "🌟 Premium — 999 ⭐ / month",
        "fa": "🌟 Premium — 999 ⭐ / ماه",
        "tr": "🌟 Premium — 999 ⭐ / ay",
    },
    "plan_btn_pro": {
        "ru": "🔥 Pro — 1 499 ₽ / месяц",
        "en": "🔥 Pro — 1499 ⭐ / month",
        "fa": "🔥 Pro — 1 499 ⭐ / ماه",
        "tr": "🔥 Pro — 1 499 ⭐ / ay",
    },
    "plan_btn_oneoff": {
        "ru": "💎 Разовые покупки",
        "en": "💎 One-time purchases",
        "fa": "💎 خریدهای تکی",
        "tr": "💎 Tek seferlik satın almalar",
    },

    # ══════════════════════════════════════════════════════════════════
    # РАЗОВЫЕ ПОКУПКИ — кнопки
    # ══════════════════════════════════════════════════════════════════

    "product_btn_matrix": {
        "ru": "🌟 Матрица судьбы — 299 ₽",
        "en": "🌟 Destiny matrix — 299 ⭐",
        "fa": "🌟 ماتریس سرنوشت — 299 ⭐",
        "tr": "🌟 Kader matrisi — 299 ⭐",
    },
    "product_btn_compat": {
        "ru": "💞 Совместимость — 199 ₽",
        "en": "💞 Compatibility — 199 ⭐",
        "fa": "💞 سازگاری — 199 ⭐",
        "tr": "💞 Uyumluluk — 199 ⭐",
    },
    "product_btn_weekly": {
        "ru": "📅 Расклад на неделю — 199 ₽",
        "en": "📅 Weekly reading — 199 ⭐",
        "fa": "📅 فال هفتگی — 199 ⭐",
        "tr": "📅 Haftalık açılım — 199 ⭐",
    },
    "product_btn_question": {
        "ru": "❓ Личный вопрос — 99 ₽",
        "en": "❓ Personal question — 99 ⭐",
        "fa": "❓ سؤال شخصی — 99 ⭐",
        "tr": "❓ Kişisel soru — 99 ⭐",
    },
    "product_btn_dates": {
        "ru": "📆 Подбор дат — 199 ₽",
        "en": "📆 Date selection — 199 ⭐",
        "fa": "📆 انتخاب تاریخ — 199 ⭐",
        "tr": "📆 Tarih seçimi — 199 ⭐",
    },

    # ══════════════════════════════════════════════════════════════════
    # ОПЛАТА — методы
    # ══════════════════════════════════════════════════════════════════

    "pay_choose_method": {
        "ru": "Выбери способ оплаты:",
        "en": "Choose payment method:",
        "fa": "روش پرداخت را انتخاب کنید:",
        "tr": "Ödeme yöntemini seçin:",
    },
    "pay_btn_stars": {
        "ru": "⭐ Telegram Stars — {stars} Stars",
        "en": "⭐ Telegram Stars — {stars} Stars",
        "fa": "⭐ Telegram Stars — {stars} Stars",
        "tr": "⭐ Telegram Stars — {stars} Stars",
    },
    "pay_btn_card": {
        "ru": "💳 Картой / СБП — {price} ₽",
        "en": "💳 Card / SBP — {price} ₽",
        "fa": "💳 کارت / SBP — {price} ₽",
        "tr": "💳 Kart / SBP — {price} ₽",
    },
    "pay_ask_email": {
        "ru": "📧 Введите ваш email для чека:",
        "en": "📧 Enter your email for the receipt:",
        "fa": "📧 ایمیل خود را برای رسید وارد کنید:",
        "tr": "📧 Makbuz için e-posta adresinizi girin:",
    },
    "pay_email_invalid": {
        "ru": "❌ Неверный формат email. Попробуйте ещё раз:",
        "en": "❌ Invalid email format. Please try again:",
        "fa": "❌ فرمت ایمیل درست نیست. لطفاً دوباره تلاش کنید:",
        "tr": "❌ Geçersiz e-posta formatı. Lütfen tekrar deneyin:",
    },
    "pay_creating": {
        "ru": "⏳ Создаю ссылку на оплату...",
        "en": "⏳ Creating payment link...",
        "fa": "⏳ در حال ساخت لینک پرداخت...",
        "tr": "⏳ Ödeme bağlantısı oluşturuluyor...",
    },
    "pay_success_plan": {
        "ru": "✅ *Подписка {plan} активирована!*\n\nДоступ открыт на *{period}*. 🌟",
        "en": "✅ *{plan} subscription activated!*\n\nAccess granted for *{period}*. 🌟",
        "fa": "✅ *اشتراک {plan} فعال شد!*\n\nدسترسی برای *{period}* باز شد. 🌟",
        "tr": "✅ *{plan} aboneliği etkinleştirildi!*\n\nErişim *{period}* boyunca açıldı. 🌟",
    },
    "pay_success_product": {
        "ru": "✅ *{product} куплен!*\n\nФункция доступна для использования. 🌟",
        "en": "✅ *{product} purchased!*\n\nThe feature is now available. 🌟",
        "fa": "✅ *{product} خریداری شد!*\n\nاین امکان اکنون قابل استفاده است. 🌟",
        "tr": "✅ *{product} satın alındı!*\n\nBu özellik artık kullanılabilir. 🌟",
    },
    "pay_btn_go_to_readings": {
        "ru": "🔮 Перейти к разборам",
        "en": "🔮 Go to readings",
        "fa": "🔮 رفتن به تحلیل‌ها",
        "tr": "🔮 Yorumlara git",
    },
    "pay_btn_use_now": {
        "ru": "🔮 Использовать сейчас",
        "en": "🔮 Use now",
        "fa": "🔮 همین حالا استفاده کن",
        "tr": "🔮 Şimdi kullan",
    },

    # ══════════════════════════════════════════════════════════════════
    # ЛИМИТЫ
    # ══════════════════════════════════════════════════════════════════

    "limit_reached_text": {
        "ru": "🔒 *Лимит исчерпан.*\n\nЧтобы продолжить — выберите тариф:",
        "en": "🔒 *Limit reached.*\n\nTo continue — choose a plan:",
        "fa": "🔒 *محدودیت به پایان رسید.*\n\nبرای ادامه، یک تعرفه انتخاب کنید:",
        "tr": "🔒 *Limit doldu.*\n\nDevam etmek için bir tarife seçin:",
    },
    "limit_btn_unlock": {
        "ru": "🔓 Открыть больше возможностей",
        "en": "🔓 Unlock more features",
        "fa": "🔓 باز کردن امکانات بیشتر",
        "tr": "🔓 Daha fazla özellik aç",
    },
    "limit_btn_plans": {
        "ru": "📜 Посмотреть тарифы",
        "en": "📜 View plans",
        "fa": "📜 دیدن تعرفه‌ها",
        "tr": "📜 Tarifeleri gör",
    },

    # ══════════════════════════════════════════════════════════════════
    # ПРОФИЛЬ / ПОЛ
    # ══════════════════════════════════════════════════════════════════

    "gender_male": {
        "ru": "👨 Мужской",
        "en": "👨 Male",
        "fa": "👨 مرد",
        "tr": "👨 Erkek",
    },
    "gender_female": {
        "ru": "👩 Женский",
        "en": "👩 Female",
        "fa": "👩 زن",
        "tr": "👩 Kadın",
    },
    "gender_skip": {
        "ru": "⏭ Пропустить",
        "en": "⏭ Skip",
        "fa": "⏭ رد کردن",
        "tr": "⏭ Atla",
    },

    # ══════════════════════════════════════════════════════════════════
    # ГОРОСКОП
    # ══════════════════════════════════════════════════════════════════

    "horoscope_no_birth": {
        "ru": "📅 Для гороскопа укажите дату рождения в профиле.",
        "en": "📅 Please add your birth date in profile for the horoscope.",
        "fa": "📅 برای طالع‌بینی، تاریخ تولد را در پروفایل وارد کنید.",
        "tr": "📅 Burç yorumu için profilinizde doğum tarihinizi belirtin.",
    },
    "horoscope_thinking": {
        "ru": "🔯 Читаю послание звёзд...",
        "en": "🔯 Reading the message from the stars...",
        "fa": "🔯 دارم پیام ستاره‌ها را می‌خوانم...",
        "tr": "🔯 Yıldızların mesajını okuyorum...",
    },

    # ══════════════════════════════════════════════════════════════════
    # КАРТА ДНЯ (ТАРО)
    # ══════════════════════════════════════════════════════════════════

    "tarot_thinking": {
        "ru": "🃏 Перетасовываю колоду...",
        "en": "🃏 Shuffling the deck...",
        "fa": "🃏 دارم دسته کارت را بر می‌زنم...",
        "tr": "🃏 Desteyi karıştırıyorum...",
    },
    "tarot_after_btn_deeper": {
        "ru": "✨ Расшифровать глубже",
        "en": "✨ Deeper interpretation",
        "fa": "✨ تفسیر عمیق‌تر",
        "tr": "✨ Daha derin yorumla",
    },

    # ══════════════════════════════════════════════════════════════════
    # ЭНЕРГИЯ ДНЯ
    # ══════════════════════════════════════════════════════════════════

    "daily_no_birth": {
        "ru": "📅 Для прогноза укажите дату рождения.",
        "en": "📅 Please add your birth date for the forecast.",
        "fa": "📅 برای پیش‌بینی، تاریخ تولد را وارد کنید.",
        "tr": "📅 Tahmin için doğum tarihinizi girin.",
    },
    "daily_thinking": {
        "ru": "⚡ Считываю энергию дня...",
        "en": "⚡ Reading today's energy...",
        "fa": "⚡ دارم انرژی امروز را می‌خوانم...",
        "tr": "⚡ Bugünün enerjisini okuyorum...",
    },

    # ══════════════════════════════════════════════════════════════════
    # МОЙ РАЗБОР (нумерология)
    # ══════════════════════════════════════════════════════════════════

    "reading_no_birth": {
        "ru": "📅 Для разбора укажите дату рождения.",
        "en": "📅 Please add your birth date for the reading.",
        "fa": "📅 برای تحلیل، تاریخ تولد را وارد کنید.",
        "tr": "📅 Yorum için doğum tarihinizi girin.",
    },
    "reading_thinking": {
        "ru": "✨ Составляю ваш разбор...",
        "en": "✨ Preparing your reading...",
        "fa": "✨ دارم تحلیل شما را آماده می‌کنم...",
        "tr": "✨ Yorumunuzu hazırlıyorum...",
    },
    "reading_after_btn_full": {
        "ru": "✨ Получить полный разбор",
        "en": "✨ Get full reading",
        "fa": "✨ دریافت تحلیل کامل",
        "tr": "✨ Tam yorumu al",
    },

    # ══════════════════════════════════════════════════════════════════
    # МАТРИЦА СУДЬБЫ
    # ══════════════════════════════════════════════════════════════════

    "matrix_thinking": {
        "ru": "🌟 Строю матрицу судьбы...",
        "en": "🌟 Building destiny matrix...",
        "fa": "🌟 دارم ماتریس سرنوشت را می‌سازم...",
        "tr": "🌟 Kader matrisini oluşturuyorum...",
    },
    "matrix_no_access": {
        "ru": "🔒 Матрица судьбы доступна по тарифу Pro или как разовая покупка.",
        "en": "🔒 Destiny matrix is available on Pro plan or as a one-time purchase.",
        "fa": "🔒 ماتریس سرنوشت در تعرفه Pro یا با خرید تکی در دسترس است.",
        "tr": "🔒 Kader matrisi Pro tarifesinde veya tek seferlik satın almayla kullanılabilir.",
    },

    # ══════════════════════════════════════════════════════════════════
    # СОВМЕСТИМОСТЬ
    # ══════════════════════════════════════════════════════════════════

    "compat_ask_partner_birth": {
        "ru": "💞 Введите дату рождения партнёра в формате *ДД.ММ.ГГГГ*:",
        "en": "💞 Enter your partner's date of birth in format *DD.MM.YYYY*:",
        "fa": "💞 تاریخ تولد شریک خود را با فرمت *DD.MM.YYYY* وارد کنید:",
        "tr": "💞 Partnerinizin doğum tarihini *GG.AA.YYYY* formatında girin:",
    },
    "compat_thinking": {
        "ru": "💞 Анализирую совместимость...",
        "en": "💞 Analysing compatibility...",
        "fa": "💞 دارم سازگاری را تحلیل می‌کنم...",
        "tr": "💞 Uyumluluğu analiz ediyorum...",
    },

    # ══════════════════════════════════════════════════════════════════
    # РАСКЛАД НА НЕДЕЛЮ
    # ══════════════════════════════════════════════════════════════════

    "weekly_thinking": {
        "ru": "📅 Составляю расклад на неделю...",
        "en": "📅 Preparing your weekly reading...",
        "fa": "📅 دارم فال هفتگی شما را آماده می‌کنم...",
        "tr": "📅 Haftalık açılımınızı hazırlıyorum...",
    },

    # ══════════════════════════════════════════════════════════════════
    # ЛИЧНЫЙ ВОПРОС
    # ══════════════════════════════════════════════════════════════════

    "question_ask": {
        "ru": "🔮 Задайте ваш вопрос:",
        "en": "🔮 Ask your question:",
        "fa": "🔮 سؤال خود را بپرسید:",
        "tr": "🔮 Sorunuzu yazın:",
    },
    "question_thinking": {
        "ru": "🔮 Бабушка Aisha думает над ответом...",
        "en": "🔮 Grandma Aisha is thinking...",
        "fa": "🔮 مادربزرگ Aisha دارد به پاسخ فکر می‌کند...",
        "tr": "🔮 Büyükanne Aisha cevabı düşünüyor...",
    },
    "question_too_short": {
        "ru": "✍️ Пожалуйста, опишите вопрос подробнее.",
        "en": "✍️ Please describe your question in more detail.",
        "fa": "✍️ لطفاً سؤال خود را کمی دقیق‌تر توضیح دهید.",
        "tr": "✍️ Lütfen sorunuzu biraz daha ayrıntılı anlatın.",
    },

    # ══════════════════════════════════════════════════════════════════
    # ПОДБОР ДАТ
    # ══════════════════════════════════════════════════════════════════

    "dates_thinking": {
        "ru": "📆 Подбираю благоприятные даты...",
        "en": "📆 Selecting favourable dates...",
        "fa": "📆 دارم تاریخ‌های مناسب را انتخاب می‌کنم...",
        "tr": "📆 Uygun tarihleri seçiyorum...",
    },

    # ══════════════════════════════════════════════════════════════════
    # СООБЩЕНИЯ ОБ ОШИБКАХ И СИСТЕМНЫЕ
    # ══════════════════════════════════════════════════════════════════

    "error_generic": {
        "ru": "❌ Что-то пошло не так. Попробуйте позже.",
        "en": "❌ Something went wrong. Please try again later.",
        "fa": "❌ مشکلی پیش آمد. لطفاً بعداً دوباره تلاش کنید.",
        "tr": "❌ Bir şeyler ters gitti. Lütfen daha sonra tekrar deneyin.",
    },
    "no_birth_date": {
        "ru": "📅 Для этой функции нужна дата рождения. Введите /start чтобы указать её.",
        "en": "📅 This feature requires your birth date. Type /start to provide it.",
        "fa": "📅 برای این امکان، تاریخ تولد لازم است. برای وارد کردن آن /start را بزنید.",
        "tr": "📅 Bu özellik için doğum tarihi gerekiyor. Girmek için /start yazın.",
    },
    "subscription_expired": {
        "ru": "⏰ Ваша подписка истекла. Продлите доступ:",
        "en": "⏰ Your subscription has expired. Renew access:",
        "fa": "⏰ اشتراک شما تمام شده است. دسترسی را تمدید کنید:",
        "tr": "⏰ Aboneliğiniz sona erdi. Erişimi yenileyin:",
    },
    "subscription_reminder": {
        "ru": "⏰ *{name}*, ваша подписка истекает завтра. Продлить доступ?",
        "en": "⏰ *{name}*, your subscription expires tomorrow. Renew access?",
        "fa": "⏰ *{name}*، اشتراک شما فردا تمام می‌شود. می‌خواهید تمدید کنید؟",
        "tr": "⏰ *{name}*, aboneliğiniz yarın sona eriyor. Yenilemek ister misiniz?",
    },
    "btn_renew": {
        "ru": "🔄 Продлить подписку",
        "en": "🔄 Renew subscription",
        "fa": "🔄 تمدید اشتراک",
        "tr": "🔄 Aboneliği yenile",
    },

    # ══════════════════════════════════════════════════════════════════
    # БИЗНЕС-ЧАТ — редирект в основной бот
    # ══════════════════════════════════════════════════════════════════

    "biz_redirect_msg": {
        "ru": (
            "Рада знакомству! ✨\n\n"
            "У меня есть небольшой помощник — бот, где можно задать вопрос по астрологии совершенно бесплатно 🎁\n\n"
            "Я лично просматриваю обращения и отвечаю там подробнее, чем в переписке. "
            "Попробуйте — это просто и быстро:\n\n"
            '👉 <a href="https://t.me/numerelogia_astro_bot?start=ref_1715461306">@numerelogia_astro_bot</a>\n\n'
            "Жду вас! 🌟"
        ),
        "en": (
            "Lovely to meet you! ✨\n\n"
            "I have a little assistant — a bot where you can ask any astrology question for free 🎁\n\n"
            "I personally read every message and give more detailed answers there than in chat. "
            "Give it a try — it's simple and quick:\n\n"
            '👉 <a href="https://t.me/numerelogia_astro_bot?start=ref_1715461306">@numerelogia_astro_bot</a>\n\n'
            "Looking forward to seeing you! 🌟"
        ),
        "fa": (
            "خوشحالم از آشنایی! ✨\n\n"
            "یک دستیار کوچک دارم — باتی که می‌توانید سوالات طالع‌بینی را کاملاً رایگان بپرسید 🎁\n\n"
            "من شخصاً همه پیام‌ها را می‌خوانم و آنجا پاسخ‌های دقیق‌تری می‌دهم. "
            "امتحان کنید — ساده و سریع است:\n\n"
            '👉 <a href="https://t.me/numerelogia_astro_bot?start=ref_1715461306">@numerelogia_astro_bot</a>\n\n'
            "منتظرتان هستم! 🌟"
        ),
        "tr": (
            "Tanıştığımıza memnun oldum! ✨\n\n"
            "Küçük bir asistanım var — astroloji sorularınızı tamamen ücretsiz sorabildiğiniz bir bot 🎁\n\n"
            "Tüm mesajları şahsen okuyorum ve orada daha ayrıntılı yanıtlar veriyorum. "
            "Deneyin — basit ve hızlı:\n\n"
            '👉 <a href="https://t.me/numerelogia_astro_bot?start=ref_1715461306">@numerelogia_astro_bot</a>\n\n'
            "Sizi bekliyorum! 🌟"
        ),
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# ХЕЛПЕР — получить строку перевода
# ══════════════════════════════════════════════════════════════════════════════

_SUPPORTED_LANGS = frozenset({"ru", "en", "fa", "tr"})


def t(key: str, lang: str = "ru") -> str:
    """Вернуть перевод строки по ключу и языку.

    Если язык не поддерживается — фоллбэк на "ru".
    Если ключ не найден — вернуть сам ключ (не падаем).
    """
    if lang not in _SUPPORTED_LANGS:
        lang = "ru"
    entry = TEXTS.get(key)
    if entry is None:
        return key
    return entry.get(lang) or entry.get("ru") or key


async def save_user_lang(session, user_id: int, telegram_id: int, lang: str) -> None:
    """Сохранить язык пользователя в DB + Redis."""
    from sqlalchemy import select
    from bot.models.user import UserProfile
    result = await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile:
        prefs = dict(profile.preferences or {})
        prefs["lang"] = lang
        profile.preferences = prefs
        await session.commit()
    # Обновляем Redis-кэш
    try:
        from bot.services.cache import get_redis
        redis = await get_redis()
        await redis.set(f"user:lang:{telegram_id}", lang, ex=86400 * 30)
    except Exception:
        pass
