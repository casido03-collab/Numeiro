"""Контентная система — раздел «Интересное»."""
import asyncio
import logging
import time
from datetime import date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.models.user import User
from bot.services.cache import get_redis

router = Router()
logger = logging.getLogger(__name__)


# ─── Статьи ───────────────────────────────────────────────────────────────────

# Article menu button labels per language
_ARTICLE_MENU_LABELS: dict[str, dict[str, str]] = {
    "numerology":    {"ru": "🔮 Тайны нумерологии",     "en": "🔮 Mysteries of Numerology", "fa": "🔮 اسرار عددشناسی",    "tr": "🔮 Numeroloji Sırları"},
    "astrology":     {"ru": "🌙 Астрология дня",        "en": "🌙 Daily Astrology",         "fa": "🌙 طالع‌بینی روز",      "tr": "🌙 Günlük Astroloji"},
    "compatibility": {"ru": "❤️ Совместимость пар",     "en": "❤️ Couple Compatibility",    "fa": "❤️ سازگاری زوج‌ها",    "tr": "❤️ Çift Uyumu"},
    "tarot":         {"ru": "🃏 Секреты Таро",           "en": "🃏 Secrets of Tarot",        "fa": "🃏 اسرار تاروت",         "tr": "🃏 Tarot Sırları"},
    "energy":        {"ru": "✨ Энергия человека",       "en": "✨ Human Energy",             "fa": "✨ انرژی انسان",          "tr": "✨ İnsan Enerjisi"},
    "destiny":       {"ru": "🌌 Судьба и знаки",        "en": "🌌 Destiny & Signs",         "fa": "🌌 سرنوشت و نشانه‌ها",  "tr": "🌌 Kader ve İşaretler"},
    "why":           {"ru": "🧠 Почему это работает?",  "en": "🧠 Why Does It Work?",       "fa": "🧠 چرا کار می‌کند؟",    "tr": "🧠 Neden İşe Yarıyor?"},
}

_ARTICLES_TEXT: dict[str, dict[str, str]] = {
    "numerology": {
        "ru": (
            "✨ *Иногда кажется, что определённые числа буквально преследуют нас.*\n\n"
            "11:11 на часах. Повторяющиеся даты. Странные совпадения.\n\n"
            "В нумерологии считается, что числа — это не просто математика, "
            "а отражение внутренних процессов человека.\n\n"
            "Каждое число несёт собственную энергетику:\n"
            "• *1* — начало и лидерство\n"
            "• *7* — интуиция и поиск смысла\n"
            "• *9* — завершение циклов\n\n"
            "Многие люди начинают замечать повторяющиеся числа именно в периоды перемен, "
            "эмоциональных переживаний или важных решений.\n\n"
            "✨ _Возможно, ваше число судьбы уже пытается подсказать вам направление._"
        ),
        "en": (
            "✨ *Sometimes it feels like certain numbers literally follow us.*\n\n"
            "11:11 on the clock. Repeating dates. Strange coincidences.\n\n"
            "In numerology, numbers are not just mathematics — they reflect a person's inner processes.\n\n"
            "Each number carries its own energy:\n"
            "• *1* — beginnings and leadership\n"
            "• *7* — intuition and search for meaning\n"
            "• *9* — completion of cycles\n\n"
            "Many people start noticing repeating numbers during times of change, "
            "emotional experiences or important decisions.\n\n"
            "✨ _Perhaps your destiny number is already trying to guide you._"
        ),
        "fa": (
            "✨ *گاهی به نظر می‌رسد اعداد خاصی ما را دنبال می‌کنند.*\n\n"
            "۱۱:۱۱ روی ساعت. تاریخ‌های تکراری. تصادفات عجیب.\n\n"
            "در عددشناسی، اعداد فقط ریاضی نیستند — آن‌ها فرآیندهای درونی انسان را منعکس می‌کنند.\n\n"
            "هر عدد انرژی خاص خود را دارد:\n"
            "• *۱* — شروع و رهبری\n"
            "• *۷* — شهود و جستجوی معنا\n"
            "• *۹* — تکمیل چرخه‌ها\n\n"
            "✨ _شاید عدد سرنوشت شما در حال راهنمایی شماست._"
        ),
        "tr": (
            "✨ *Bazen belirli sayıların bizi takip ettiğini hissederiz.*\n\n"
            "Saatte 11:11. Tekrar eden tarihler. Garip tesadüfler.\n\n"
            "Numerolojide sayılar sadece matematik değil — insanın iç süreçlerinin yansımasıdır.\n\n"
            "Her sayı kendi enerjisini taşır:\n"
            "• *1* — başlangıçlar ve liderlik\n"
            "• *7* — sezgi ve anlam arayışı\n"
            "• *9* — döngülerin tamamlanması\n\n"
            "✨ _Belki kader sayınız size zaten yön göstermeye çalışıyor._"
        ),
    },
    "astrology": {
        "ru": (
            "🌙 *Вы замечали, как в некоторые дни всё буквально валится из рук?*\n\n"
            "А иногда наоборот — энергия словно подталкивает к действиям.\n\n"
            "Астрология связывает это с положением планет и Луны.\n\n"
            "Например:\n"
            "• *Полнолуние* часто усиливает эмоции\n"
            "• *Ретроградные периоды* создают ощущение задержек и хаоса\n\n"
            "Даже люди, которые не верят в астрологию, нередко замечают изменение "
            "настроения в определённые периоды.\n\n"
            "✨ _Возможно, сегодня именно тот день, когда стоит прислушаться к себе внимательнее._"
        ),
        "en": (
            "🌙 *Have you noticed how some days everything just falls apart?*\n\n"
            "And on others — energy seems to push you forward.\n\n"
            "Astrology connects this to the position of planets and the Moon.\n\n"
            "For example:\n"
            "• *Full Moon* often intensifies emotions\n"
            "• *Retrograde periods* create a feeling of delays and chaos\n\n"
            "Even people who don't believe in astrology often notice mood changes during certain periods.\n\n"
            "✨ _Perhaps today is exactly the day to listen to yourself more carefully._"
        ),
        "fa": (
            "🌙 *آیا متوجه شده‌اید که برخی روزها همه چیز از دست می‌رود؟*\n\n"
            "و در روزهای دیگر — انرژی شما را به جلو هل می‌دهد.\n\n"
            "ستاره‌شناسی این را به موقعیت سیارات و ماه مرتبط می‌داند.\n\n"
            "مثلاً:\n"
            "• *ماه کامل* اغلب احساسات را تقویت می‌کند\n"
            "• *دوره‌های رتروگراد* احساس تأخیر ایجاد می‌کنند\n\n"
            "✨ _شاید امروز روزی است که باید به خودتان بیشتر گوش دهید._"
        ),
        "tr": (
            "🌙 *Bazı günlerin neden her şeyin ters gittiğini fark ettiniz mi?*\n\n"
            "Diğer günlerde ise enerji sizi ileri iter gibi hissedersiniz.\n\n"
            "Astroloji bunu gezegenlerin ve Ay'ın konumuyla ilişkilendirir.\n\n"
            "Örneğin:\n"
            "• *Dolunay* çoğunlukla duyguları yoğunlaştırır\n"
            "• *Retrograd dönemler* gecikme hissi yaratır\n\n"
            "✨ _Belki bugün kendinizi daha dikkatli dinlemeniz gereken gün._"
        ),
    },
    "compatibility": {
        "ru": (
            "❤️ *Некоторые люди появляются в нашей жизни словно не случайно.*\n\n"
            "С кем-то связь возникает мгновенно.\n"
            "А с кем-то отношения становятся эмоционально тяжёлыми и запутанными.\n\n"
            "В эзотерических практиках считается, что между людьми может существовать "
            "энергетическая совместимость.\n\n"
            "Иногда партнёры усиливают друг друга.\n"
            "А иногда — запускают внутренние конфликты и уроки.\n\n"
            "Именно поэтому некоторые отношения ощущаются как судьбоносные.\n\n"
            "✨ _Возможно, ваша связь тоже скрывает более глубокий смысл._"
        ),
        "en": (
            "❤️ *Some people appear in our lives as if not by chance.*\n\n"
            "With some, a connection forms instantly.\n"
            "With others, relationships become emotionally heavy and tangled.\n\n"
            "In esoteric practices, it's believed that energetic compatibility can exist between people.\n\n"
            "Sometimes partners strengthen each other.\n"
            "And sometimes — they trigger inner conflicts and lessons.\n\n"
            "That's why some relationships feel like destiny.\n\n"
            "✨ _Perhaps your connection also hides a deeper meaning._"
        ),
        "fa": (
            "❤️ *برخی افراد گویی نه تصادفی وارد زندگی ما می‌شوند.*\n\n"
            "با بعضی‌ها ارتباط فوری برقرار می‌شود.\n"
            "با دیگران روابط سنگین و پیچیده می‌شود.\n\n"
            "در عرفان باور بر این است که سازگاری انرژتیک بین افراد وجود دارد.\n\n"
            "گاهی شرکا یکدیگر را تقویت می‌کنند.\n"
            "و گاهی — درگیری‌های درونی ایجاد می‌کنند.\n\n"
            "✨ _شاید رابطه شما نیز معنایی عمیق‌تر دارد._"
        ),
        "tr": (
            "❤️ *Bazı insanlar sanki tesadüfen değil hayatımıza girer.*\n\n"
            "Bazılarıyla bağlantı anında kurulur.\n"
            "Diğerleriyle ilişkiler duygusal olarak ağır ve karmaşık hale gelir.\n\n"
            "Ezoterik uygulamalarda insanlar arasında enerjetik uyumun var olduğuna inanılır.\n\n"
            "Bazen partnerler birbirini güçlendirir.\n"
            "Bazen ise iç çatışmalar ve dersler tetiklenir.\n\n"
            "✨ _Belki sizin bağlantınız da daha derin bir anlam taşıyor._"
        ),
    },
    "tarot": {
        "ru": (
            "🃏 *Карты Таро уже много веков используются как инструмент символов и подсознания.*\n\n"
            "Иногда один расклад способен удивительно точно описать внутреннее состояние человека.\n\n"
            "Таро не предсказывает будущее буквально.\n"
            "Скорее оно помогает увидеть:\n"
            "• скрытые эмоции\n"
            "• внутренние страхи\n"
            "• вероятные сценарии\n"
            "• подсказки для принятия решений\n\n"
            "Именно поэтому многие люди чувствуют странное совпадение между картами и "
            "событиями своей жизни.\n\n"
            "✨ _Возможно, ответы уже находятся внутри вас._"
        ),
        "en": (
            "🃏 *Tarot cards have been used as a tool of symbols and the subconscious for many centuries.*\n\n"
            "Sometimes a single reading can describe a person's inner state with surprising accuracy.\n\n"
            "Tarot doesn't literally predict the future.\n"
            "Rather, it helps to see:\n"
            "• hidden emotions\n"
            "• inner fears\n"
            "• likely scenarios\n"
            "• hints for making decisions\n\n"
            "That's why many people feel a strange coincidence between the cards and events of their life.\n\n"
            "✨ _Perhaps the answers are already inside you._"
        ),
        "fa": (
            "🃏 *کارت‌های تاروت قرن‌هاست به عنوان ابزار نمادها و ناخودآگاه استفاده می‌شوند.*\n\n"
            "گاهی یک تفسیر می‌تواند حالت درونی انسان را با دقت شگفت‌انگیزی توصیف کند.\n\n"
            "تاروت آینده را به معنای واقعی پیش‌بینی نمی‌کند.\n"
            "بلکه کمک می‌کند ببینید:\n"
            "• احساسات پنهان\n"
            "• ترس‌های درونی\n"
            "• سناریوهای احتمالی\n"
            "• راهنمایی برای تصمیم‌گیری\n\n"
            "✨ _شاید پاسخ‌ها از قبل درون شما هستند._"
        ),
        "tr": (
            "🃏 *Tarot kartları yüzyıllardır semboller ve bilinçaltı aracı olarak kullanılmaktadır.*\n\n"
            "Bazen tek bir okuma, kişinin iç durumunu şaşırtıcı bir doğrulukla tanımlayabilir.\n\n"
            "Tarot geleceği gerçek anlamda tahmin etmez.\n"
            "Aksine görmenize yardımcı olur:\n"
            "• gizli duygular\n"
            "• iç korkular\n"
            "• olası senaryolar\n"
            "• karar verme için ipuçları\n\n"
            "✨ _Belki cevaplar zaten içinizde._"
        ),
    },
    "energy": {
        "ru": (
            "✨ *У каждого человека есть собственная энергетика.*\n\n"
            "Некоторые люди буквально заряжают нас энергией.\n"
            "А после общения с другими появляется усталость и эмоциональная тяжесть.\n\n"
            "В эзотерике считается, что внутреннее состояние человека напрямую связано:\n"
            "• с эмоциями\n"
            "• окружением\n"
            "• мыслями\n"
            "• жизненными циклами\n\n"
            "Иногда смена энергетики ощущается ещё до того, как происходят реальные события.\n\n"
            "✨ _Возможно, сейчас вы входите в новый жизненный этап._"
        ),
        "en": (
            "✨ *Every person has their own energy.*\n\n"
            "Some people literally charge us with energy.\n"
            "After communicating with others, fatigue and emotional heaviness appear.\n\n"
            "In esoterics, a person's inner state is directly connected to:\n"
            "• emotions\n"
            "• environment\n"
            "• thoughts\n"
            "• life cycles\n\n"
            "Sometimes an energy shift is felt even before real events happen.\n\n"
            "✨ _Perhaps you are now entering a new phase of life._"
        ),
        "fa": (
            "✨ *هر انسانی انرژی خاص خودش را دارد.*\n\n"
            "برخی افراد ما را شارژ می‌کنند.\n"
            "بعد از ارتباط با دیگران خستگی و سنگینی احساسی به وجود می‌آید.\n\n"
            "در عرفان حالت درونی انسان مستقیماً مرتبط است با:\n"
            "• احساسات\n"
            "• محیط\n"
            "• افکار\n"
            "• چرخه‌های زندگی\n\n"
            "✨ _شاید الان وارد مرحله جدیدی از زندگی می‌شوید._"
        ),
        "tr": (
            "✨ *Her insanın kendine özgü bir enerjisi vardır.*\n\n"
            "Bazı insanlar bizi adeta enerjiyle doldurur.\n"
            "Diğerleriyle iletişimden sonra yorgunluk ve duygusal ağırlık gelir.\n\n"
            "Ezoterik anlayışa göre kişinin iç durumu doğrudan bağlantılıdır:\n"
            "• duygular\n"
            "• çevre\n"
            "• düşünceler\n"
            "• yaşam döngüleri\n\n"
            "✨ _Belki şu an yeni bir yaşam evresine giriyorsunuz._"
        ),
    },
    "destiny": {
        "ru": (
            "🌌 *Многие люди замечают странные совпадения:*\n\n"
            "• одинаковые числа\n"
            "• повторяющиеся ситуации\n"
            "• случайные встречи\n"
            "• неожиданные знаки\n\n"
            "Иногда кажется, будто жизнь пытается обратить наше внимание на что-то важное.\n\n"
            "В эзотерике подобные события называют знаками судьбы.\n\n"
            "Особенно часто они появляются в периоды:\n"
            "• внутренних перемен\n"
            "• сильных эмоций\n"
            "• важных решений\n\n"
            "✨ _Возможно, некоторые события в вашей жизни уже несут скрытый смысл._"
        ),
        "en": (
            "🌌 *Many people notice strange coincidences:*\n\n"
            "• same numbers\n"
            "• repeating situations\n"
            "• chance meetings\n"
            "• unexpected signs\n\n"
            "Sometimes it seems as if life is trying to draw our attention to something important.\n\n"
            "In esoterics, such events are called destiny signs.\n\n"
            "They most often appear during periods of:\n"
            "• inner change\n"
            "• strong emotions\n"
            "• important decisions\n\n"
            "✨ _Perhaps some events in your life already carry a hidden meaning._"
        ),
        "fa": (
            "🌌 *بسیاری از مردم تصادفات عجیبی را می‌بینند:*\n\n"
            "• اعداد یکسان\n"
            "• موقعیت‌های تکراری\n"
            "• ملاقات‌های تصادفی\n"
            "• نشانه‌های غیرمنتظره\n\n"
            "گاهی به نظر می‌رسد زندگی سعی دارد توجه ما را به چیز مهمی جلب کند.\n\n"
            "در عرفان، چنین رویدادهایی نشانه‌های سرنوشت نامیده می‌شوند.\n\n"
            "✨ _شاید برخی رویدادها در زندگی شما معنای پنهانی دارند._"
        ),
        "tr": (
            "🌌 *Pek çok kişi garip tesadüfler fark eder:*\n\n"
            "• aynı sayılar\n"
            "• tekrar eden durumlar\n"
            "• tesadüfi buluşmalar\n"
            "• beklenmedik işaretler\n\n"
            "Bazen sanki hayat dikkatimizi önemli bir şeye çekmeye çalışıyor gibi görünür.\n\n"
            "Ezoterik anlayışta bu tür olaylar kader işaretleri olarak adlandırılır.\n\n"
            "✨ _Belki hayatınızdaki bazı olaylar zaten gizli bir anlam taşıyor._"
        ),
    },
    "why": {
        "ru": (
            "🧠 *Даже люди, которые относятся к эзотерике скептически,*\n"
            "часто замечают странное чувство узнавания.\n\n"
            "Почему некоторые расклады кажутся настолько точными?\n\n"
            "Частично это связано с тем, что человек начинает глубже анализировать "
            "себя и собственные эмоции.\n\n"
            "Эзотерические практики часто работают как способ:\n"
            "• обратить внимание на внутренние переживания\n"
            "• замедлиться\n"
            "• посмотреть на ситуацию под другим углом\n\n"
            "Иногда именно это помогает человеку принять важное решение.\n\n"
            "✨ _Возможно, ответы находятся ближе, чем кажется._"
        ),
        "en": (
            "🧠 *Even people who are skeptical about esoterics*\n"
            "often notice a strange feeling of recognition.\n\n"
            "Why do some readings seem so accurate?\n\n"
            "Partly because a person begins to analyze themselves and their emotions more deeply.\n\n"
            "Esoteric practices often work as a way to:\n"
            "• pay attention to inner experiences\n"
            "• slow down\n"
            "• look at the situation from a different angle\n\n"
            "Sometimes this is exactly what helps a person make an important decision.\n\n"
            "✨ _Perhaps the answers are closer than they seem._"
        ),
        "fa": (
            "🧠 *حتی افرادی که نسبت به عرفان شک دارند،*\n"
            "اغلب احساس عجیبی از شناسایی می‌کنند.\n\n"
            "چرا برخی تفسیرها اینقدر دقیق به نظر می‌رسند؟\n\n"
            "جزئاً به این دلیل است که انسان شروع می‌کند خود و احساساتش را عمیق‌تر تحلیل کند.\n\n"
            "تمرینات عرفانی اغلب به عنوان راهی عمل می‌کنند برای:\n"
            "• توجه به تجربیات درونی\n"
            "• کند شدن\n"
            "• نگاه به موقعیت از زاویه دیگر\n\n"
            "✨ _شاید پاسخ‌ها نزدیک‌تر از آنچه به نظر می‌رسد هستند._"
        ),
        "tr": (
            "🧠 *Ezoteriğe kuşkuyla yaklaşan insanlar bile*\n"
            "sık sık garip bir tanıma hissi fark eder.\n\n"
            "Bazı okumalar neden bu kadar doğru görünür?\n\n"
            "Kısmen çünkü kişi kendini ve duygularını daha derin analiz etmeye başlar.\n\n"
            "Ezoterik uygulamalar genellikle şunlar için bir yol olarak işlev görür:\n"
            "• iç deneyimlere dikkat etmek\n"
            "• yavaşlamak\n"
            "• duruma farklı bir açıdan bakmak\n\n"
            "✨ _Belki cevaplar göründüğünden daha yakın._"
        ),
    },
}

# ── Article action buttons per article/lang ────────────────────────────────────

def _article_buttons(key: str, lang: str) -> list[list[InlineKeyboardButton]]:
    _back   = {"ru": "◀️ Назад",         "en": "◀️ Back",         "fa": "◀️ بازگشت",       "tr": "◀️ Geri"}.get(lang, "◀️ Back")
    _share  = {"ru": "📤 Поделиться",    "en": "📤 Share",         "fa": "📤 اشتراک‌گذاری", "tr": "📤 Paylaş"}.get(lang, "📤 Share")

    _btn_matrix = {"ru": "🔮 Матрица судьбы",         "en": "🔮 Destiny Matrix",   "fa": "🔮 ماتریس سرنوشت",  "tr": "🔮 Kader Matrisi"}.get(lang, "🔮 Destiny Matrix")
    _btn_weekly = {"ru": "🌙 Получить прогноз",        "en": "🌙 Get forecast",     "fa": "🌙 دریافت پیش‌بینی","tr": "🌙 Tahmin al"}.get(lang, "🌙 Get forecast")
    _btn_daily  = {"ru": "✨ Энергия дня",             "en": "✨ Daily energy",      "fa": "✨ انرژی روز",       "tr": "✨ Günün enerjisi"}.get(lang, "✨ Daily energy")
    _btn_compat = {"ru": "❤️ Проверить совместимость", "en": "❤️ Check compatibility","fa": "❤️ بررسی سازگاری","tr": "❤️ Uyum kontrol"}.get(lang, "❤️ Check compatibility")
    _btn_quest  = {"ru": "🔮 Задать вопрос",           "en": "🔮 Ask a question",   "fa": "🔮 سؤال بپرسید",    "tr": "🔮 Soru sor"}.get(lang, "🔮 Ask a question")
    _btn_read   = {"ru": "🔮 Рассчитать число судьбы", "en": "🔮 Calculate destiny number","fa": "🔮 محاسبه عدد سرنوشت","tr": "🔮 Kader sayısı hesapla"}.get(lang, "🔮 Calculate destiny number")
    _btn_sign   = {"ru": "🌌 Получить знак дня",       "en": "🌌 Get sign of the day","fa": "🌌 دریافت نشانه روز","tr": "🌌 Günün işaretini al"}.get(lang, "🌌 Get sign of the day")
    _btn_try    = {"ru": "🔮 Попробовать на себе",     "en": "🔮 Try it yourself",   "fa": "🔮 امتحان کنید",    "tr": "🔮 Kendiniz deneyin"}.get(lang, "🔮 Try it yourself")

    _MAP: dict[str, list[list]] = {
        "numerology":    [[_btn_read, "menu:reading"], [_btn_weekly, "menu:weekly"]],
        "astrology":     [[_btn_weekly, "menu:weekly"], [_btn_daily, "menu:daily"]],
        "compatibility": [[_btn_compat, "compat:start"], [_btn_quest, "menu:question"]],
        "tarot":         [[_btn_read, "menu:reading"], [_btn_weekly, "menu:weekly"]],
        "energy":        [[_btn_try, "menu:reading"], [_btn_matrix, "matrix:start"]],
        "destiny":       [[_btn_sign, "menu:daily"], [_btn_quest, "menu:question"]],
        "why":           [[_btn_try, "menu:reading"], [_btn_weekly, "menu:weekly"]],
    }
    rows = [[InlineKeyboardButton(text=btn, callback_data=cb)] for btn, cb in _MAP.get(key, [])]
    rows.append([InlineKeyboardButton(text=_share, callback_data=f"share:content:{key}")])
    rows.append([InlineKeyboardButton(text=_back, callback_data="content:menu")])
    return rows


def _get_article_text(key: str, lang: str) -> str:
    texts = _ARTICLES_TEXT.get(key, {})
    return texts.get(lang) or texts.get("en") or texts.get("ru", "")


def _get_article_title(key: str, lang: str) -> str:
    return _ARTICLE_MENU_LABELS.get(key, {}).get(lang) or _ARTICLE_MENU_LABELS.get(key, {}).get("en", key)


# Legacy ARTICLES dict for backward compatibility (share handler uses article['title'])
ARTICLES = {
    key: {
        "title": _ARTICLE_MENU_LABELS[key]["ru"],
        "text":  _ARTICLES_TEXT[key]["ru"],
        "buttons": _article_buttons(key, "ru"),
    }
    for key in _ARTICLES_TEXT
}

ARTICLE_BUTTON_LABELS = {k: v["ru"] for k, v in _ARTICLE_MENU_LABELS.items()}


# ─── Трекинг просмотров ────────────────────────────────────────────────────────

async def track_view(article_key: str):
    try:
        r = await get_redis()
        today = date.today().isoformat()
        await r.incr(f"content:views:{today}:{article_key}")
    except Exception as e:
        logger.debug("Content view tracking failed: %s", e)


async def get_popular_today() -> list[tuple[str, int]]:
    """Return top-3 articles by view count today."""
    try:
        r = await get_redis()
        today = date.today().isoformat()
        counts = []
        for key in ARTICLES:
            n = await r.get(f"content:views:{today}:{key}")
            counts.append((key, int(n) if n else 0))
        counts.sort(key=lambda x: x[1], reverse=True)
        return counts[:3]
    except Exception:
        return [("numerology", 0), ("compatibility", 0), ("astrology", 0)]


# ─── Клавиатуры ────────────────────────────────────────────────────────────────

def content_menu_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    L = _ARTICLE_MENU_LABELS
    _popular = {"ru": "🔥 Популярное сегодня", "en": "🔥 Popular today", "fa": "🔥 محبوب امروز", "tr": "🔥 Bugün popüler"}.get(lang, "🔥 Popular today")

    def _btn(key: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(text=L[key].get(lang, L[key]["en"]), callback_data=f"content:{key}")

    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("numerology")],
        [_btn("astrology")],
        [_btn("compatibility"), _btn("tarot")],
        [_btn("energy"),        _btn("destiny")],
        [_btn("why")],
        [InlineKeyboardButton(text=_popular, callback_data="content:popular")],
    ])


# ─── Обработчики reply-кнопки ─────────────────────────────────────────────────

@router.message(F.text.in_({"📚 Интересное", "📚 Interesting", "📚 جالب", "📚 İlginç"}))
async def reply_interesting(message: Message, state: FSMContext, lang: str = "ru"):
    t0 = time.monotonic()
    logger.info("MENU_HANDLER_STARTED handler=reply_interesting user=%s", message.from_user.id)
    try:
        await asyncio.wait_for(state.clear(), timeout=3.0)
    except Exception:
        pass
    from bot.utils import show_menu_message
    _heading = {"ru": "✨ *Выберите тему, которая вам интересна:*",
                "en": "✨ *Choose a topic you are interested in:*",
                "fa": "✨ *موضوعی که علاقه دارید را انتخاب کنید:*",
                "tr": "✨ *İlgilendiğiniz bir konu seçin:*"}.get(lang, "✨ *Choose a topic you are interested in:*")
    await show_menu_message(
        message, message.from_user.id,
        _heading,
        content_menu_kb(lang),
        force_new=True,
        fast=True,
    )
    logger.info("MENU_RENDER_DONE handler=reply_interesting duration_ms=%.0f", (time.monotonic() - t0) * 1000)


@router.message(F.text.in_({"🔮 Меню", "🔮 Menu", "🔮 منو", "🔮 Menü"}))
async def reply_menu(message: Message, user: User, state: FSMContext, lang: str = "ru"):
    """Кнопка «🔮 Меню» работает как /start — полный welcome-экран + клавиатура."""
    t0 = time.monotonic()
    logger.info("MENU_HANDLER_STARTED handler=reply_menu user=%s", message.from_user.id)
    try:
        await asyncio.wait_for(state.clear(), timeout=3.0)
    except Exception:
        pass
    from bot.keyboards.main import main_menu
    from bot.keyboards.reply import main_reply_keyboard
    from bot.handlers.start import _welcome_text
    from bot.services.menu_tracker import is_keyboard_shown, mark_keyboard_shown
    from bot.utils import show_menu_message, safe_answer_menu

    # Проверка спонсорской подписки
    from bot.handlers.sponsor import get_sponsor_state, is_subscribed, sponsor_keyboard
    sponsor = await get_sponsor_state()
    if sponsor["enabled"] and sponsor["channel"]:
        subscribed = await is_subscribed(message.bot, message.from_user.id, sponsor["channel"])
        if not subscribed:
            await message.answer(
                "Чтобы продолжить, подпишитесь на канал:",
                reply_markup=sponsor_keyboard(sponsor["link"]),
            )
            return

    name = user.first_name or None
    # Клавиатуру отправляем только если она не была показана ранее
    if not await is_keyboard_shown(user.telegram_id):
        sent = await safe_answer_menu(message, "🌙", reply_markup=main_reply_keyboard(lang), parse_mode=None)
        if sent:
            await mark_keyboard_shown(user.telegram_id)
    # Полный welcome-текст + inline меню одним новым сообщением
    await show_menu_message(
        message, user.telegram_id,
        _welcome_text(name, lang),
        main_menu(lang),
        force_new=True,
        fast=True,
    )
    logger.info("MENU_RENDER_DONE handler=reply_menu duration_ms=%.0f", (time.monotonic() - t0) * 1000)


# ─── Обработчик inline-меню контента ─────────────────────────────────────────

@router.callback_query(F.data == "content:menu")
async def show_content_menu(callback: CallbackQuery, lang: str = "ru"):
    _heading = {"ru": "✨ *Выберите тему, которая вам интересна:*",
                "en": "✨ *Choose a topic you are interested in:*",
                "fa": "✨ *موضوعی که علاقه دارید را انتخاب کنید:*",
                "tr": "✨ *İlgilendiğiniz bir konu seçin:*"}.get(lang, "✨ *Choose a topic you are interested in:*")
    await callback.message.edit_text(
        _heading,
        reply_markup=content_menu_kb(lang),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content:") & ~F.data.startswith("content:popular"))
async def show_article(callback: CallbackQuery, lang: str = "ru"):
    article_key = callback.data.split(":")[-1]
    if article_key == "menu":
        return  # обработан выше

    if article_key not in _ARTICLES_TEXT:
        await callback.answer("Article not found")
        return

    await track_view(article_key)

    text = _get_article_text(article_key, lang)
    kb = InlineKeyboardMarkup(inline_keyboard=_article_buttons(article_key, lang))
    from bot.utils import safe_edit
    await safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "content:popular")
async def show_popular(callback: CallbackQuery, lang: str = "ru"):
    popular = await get_popular_today()

    _back = {"ru": "◀️ Назад", "en": "◀️ Back", "fa": "◀️ بازگشت", "tr": "◀️ Geri"}.get(lang, "◀️ Back")

    lines = []
    for key, _ in popular:
        label = _get_article_title(key, lang)
        lines.append(f"• {label}")

    if not any(count > 0 for _, count in popular):
        _default_text = {
            "ru": ("🔥 *Сегодня чаще всего пользователи читают:*\n\n"
                   "• ❤️ Совместимость после расставания\n"
                   "• 🌙 Прогноз на ближайшие 7 дней\n"
                   "• 👁 Значение числа 11:11"),
            "en": ("🔥 *Most popular reads today:*\n\n"
                   "• ❤️ Compatibility after a breakup\n"
                   "• 🌙 Forecast for the next 7 days\n"
                   "• 👁 Meaning of the number 11:11"),
            "fa": ("🔥 *پربازدیدترین مطالب امروز:*\n\n"
                   "• ❤️ سازگاری پس از جدایی\n"
                   "• 🌙 پیش‌بینی ۷ روز آینده\n"
                   "• 👁 معنای عدد ۱۱:۱۱"),
            "tr": ("🔥 *Bugün en çok okunanlar:*\n\n"
                   "• ❤️ Ayrılık sonrası uyum\n"
                   "• 🌙 Önümüzdeki 7 gün tahmini\n"
                   "• 👁 11:11 sayısının anlamı"),
        }.get(lang, "🔥 *Most popular reads today:*")
        _compat = {"ru": "❤️ Открыть совместимость", "en": "❤️ Check compatibility",
                   "fa": "❤️ بررسی سازگاری", "tr": "❤️ Uyum kontrol"}.get(lang, "❤️ Check compatibility")
        _weekly = {"ru": "🌙 Получить прогноз", "en": "🌙 Get forecast",
                   "fa": "🌙 دریافت پیش‌بینی", "tr": "🌙 Tahmin al"}.get(lang, "🌙 Get forecast")
        _numer  = _get_article_title("numerology", lang)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_compat, callback_data="compat:start")],
            [InlineKeyboardButton(text=_weekly, callback_data="menu:weekly")],
            [InlineKeyboardButton(text=_numer,  callback_data="content:numerology")],
            [InlineKeyboardButton(text=_back,   callback_data="content:menu")],
        ])
        text = _default_text
    else:
        _pop_title = {"ru": "🔥 *Популярное сегодня:*", "en": "🔥 *Popular today:*",
                      "fa": "🔥 *محبوب امروز:*", "tr": "🔥 *Bugün popüler:*"}.get(lang, "🔥 *Popular today:*")
        text = _pop_title + "\n\n" + "\n".join(lines)
        buttons = [
            [InlineKeyboardButton(text=_get_article_title(k, lang), callback_data=f"content:{k}")]
            for k, _ in popular
        ]
        buttons.append([InlineKeyboardButton(text=_back, callback_data="content:menu")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ─── Share контента ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("share:content:"))
async def share_content(callback: CallbackQuery, user: User, lang: str = "ru"):
    await callback.answer()  # сразу, до async-работы

    try:
        article_key = callback.data.split(":")[-1]
        if article_key not in _ARTICLES_TEXT:
            return

        import html as _html
        from bot.handlers.share import _get_bot_username
        bot_username = await _get_bot_username(callback.bot)
        bot_link = f"https://t.me/{bot_username}"
        ref_link = f"{bot_link}?start=ref_{user.telegram_id}"
        title = _get_article_title(article_key, lang)

        _share_header = {
            "ru": "📤 <b>Поделись с друзьями:</b>",
            "en": "📤 <b>Share with friends:</b>",
            "fa": "📤 <b>با دوستان به اشتراک بگذارید:</b>",
            "tr": "📤 <b>Arkadaşlarınla paylaş:</b>",
        }.get(lang, "📤 <b>Share with friends:</b>")
        _share_cta = {
            "ru": f'Читай эзотерические разборы в боте <a href="{bot_link}">Aisha AI 🔮</a>',
            "en": f'Read esoteric readings in the bot <a href="{bot_link}">Aisha AI 🔮</a>',
            "fa": f'تفسیرهای عرفانی را در ربات بخوانید <a href="{bot_link}">Aisha AI 🔮</a>',
            "tr": f'Ezoterik yorumları botta oku <a href="{bot_link}">Aisha AI 🔮</a>',
        }.get(lang, f'<a href="{bot_link}">Aisha AI 🔮</a>')

        await callback.message.answer(
            f"{_share_header}\n\n"
            f"<i>{_html.escape(title)}</i>\n\n"
            f"{_share_cta}\n\n"
            f"👉 {ref_link}",
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
    except Exception:
        pass


# ─── Контентные CTA после действий ───────────────────────────────────────────

def compatibility_cta_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❤️ Что такое кармические отношения?",
            callback_data="content:compatibility",
        )],
    ])


def weekly_cta_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🌙 Как Луна влияет на настроение?",
            callback_data="content:astrology",
        )],
    ])


def reading_cta_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👁 Тайна 11:11",
            callback_data="content:numerology",
        )],
    ])
