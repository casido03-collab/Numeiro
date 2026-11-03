"""Customer-facing contracts use the same prices as checkout."""
from config import PRODUCTS

DETAILS = {
    "personal_question": ("Один вопрос: законченный разбор ситуации и три практических шага. Одно уточнение по этому ответу включено в течение 24 часов.",
                         "One question: a complete reading and three practical steps. One clarification about this answer is included within 24 hours.",
                         "یک سؤال: تفسیر کامل و سه اقدام عملی؛ یک سؤال تکمیلی تا ۲۴ ساعت در قیمت گنجانده شده است.",
                         "Bir soru: tam yorum ve üç pratik adım. 24 saat içinde bu yanıtla ilgili bir açıklama dahildir."),
    "mini_reading": ("Полный мини-разбор одной сферы: сильные стороны, возможные трудности и три действия на неделю.",
                     "A complete reading of one area: strengths, possible difficulties and three actions for the week.",
                     "تفسیر کامل یک حوزه: نقاط قوت، دشواری‌های احتمالی و سه اقدام برای هفته.",
                     "Bir alanın tam yorumu: güçlü yanlar, olası zorluklar ve hafta için üç adım."),
    "tarot_card": ("Одна карта дня: смысл, вопрос для размышления и действие на сегодня. Повторный просмотр той же карты — без списания.",
                   "One daily card: meaning, reflection and an action for today. Reopening the same card uses no extra credit.",
                   "یک کارت روز: معنا، موضوعی برای تأمل و اقدام امروز. مشاهده مجدد همان کارت رایگان است.",
                   "Bir günlük kart: anlamı, düşünme sorusu ve bugünün adımı. Aynı kartı yeniden açmak hak tüketmez."),
    "full_matrix": ("Девять разделов по вашей матрице: способности, отношения, работа и план действий на неделю.",
                    "Nine sections covering your matrix: abilities, relationships, work and a weekly action plan.",
                    "نه بخش درباره ماتریس شما: توانایی‌ها، روابط، کار و برنامه عملی هفته.",
                    "Matrisinizin dokuz bölümü: yetenekler, ilişkiler, iş ve haftalık eylem planı."),
    "compatibility": ("Разбор пары по двум датам и типу отношений: точки поддержки, разногласия и конкретные договорённости.",
                      "A reading based on two dates and relationship type: strengths, disagreements and practical agreements.",
                      "تفسیر بر اساس دو تاریخ و نوع رابطه: نقاط قوت، اختلافات و توافق‌های عملی.",
                      "İki tarih ve ilişki türüne göre yorum: destek noktaları, anlaşmazlıklar ve pratik anlaşmalar."),
    "weekly_report": ("Семь дней от даты запроса: отдельная рекомендация на каждый день, возможности, риски и план действий.",
                      "Seven days from your request: advice for each day, opportunities, risks and an action plan.",
                      "هفت روز از تاریخ درخواست: پیشنهاد هر روز، فرصت‌ها، ریسک‌ها و برنامه عملی.",
                      "İsteğinizden itibaren yedi gün: her güne öneri, fırsatlar, riskler ve eylem planı."),
    "date_selection": ("Пять дат в ближайшие 60 дней для выбранного события: символическое обоснование и подготовка. Практическая доступность важнее чисел.",
                       "Five dates within the next 60 days for your event: symbolic reasoning and preparation. Practical availability comes first.",
                       "پنج تاریخ در ۶۰ روز آینده برای رویداد شما: تفسیر نمادین و آمادگی. امکان عملی اولویت دارد.",
                       "Etkinliğiniz için önümüzdeki 60 günden beş tarih: sembolik yorum ve hazırlık. Pratik uygunluk önceliklidir."),
}
NAMES = {
    "en": ["Personal question", "Mini reading", "Daily card", "Full matrix", "Compatibility", "Weekly reading", "Date selection"],
    "fa": ["سؤال شخصی", "تفسیر کوتاه", "کارت روز", "ماتریس کامل", "سازگاری", "تفسیر هفتگی", "انتخاب تاریخ"],
    "tr": ["Kişisel soru", "Kısa okuma", "Günün kartı", "Tam matris", "Uyumluluk", "Haftalık okuma", "Tarih seçimi"],
}
FREE_SUMMARY = {
    "ru": "Бесплатно: гороскоп дня и одна «Энергия дня» в день. Личный вопрос, мини-разбор и остальные разборы — по указанной цене или в пределах VIP.",
    "en": "Free: the daily horoscope and one Daily Energy reading per day. Personal questions and other readings are paid individually or included within VIP quotas.",
    "fa": "رایگان: طالع‌بینی روزانه و یک «انرژی روز» در روز. سؤال شخصی و سایر تفسیرها با پرداخت یا در سهمیه VIP ارائه می‌شوند.",
    "tr": "Ücretsiz: günlük burç ve günde bir Günün Enerjisi. Kişisel sorular ve diğer okumalar ücretli veya VIP kotası dahilindedir.",
}


def product_offer(key, lang="ru"):
    lang = lang if lang in ("ru", "en", "fa", "tr") else "en"
    index = ("ru", "en", "fa", "tr").index(lang)
    product = PRODUCTS[key]
    name = product["name"] if lang == "ru" else NAMES[lang][list(DETAILS).index(key)]
    price = f'{product["price_rub"]} ₽ / {product["price_stars"]} ⭐' if lang == "ru" else f'{product["price_stars"]} ⭐'
    ending = (
        "Результат сохранится в «Мои разборы». Символическая интерпретация, без гарантий будущих событий.",
        "Your result is saved in My Readings. A symbolic interpretation, without guarantees about future events.",
        "نتیجه در تاریخچه ذخیره می‌شود. این تفسیر نمادین است و آینده را تضمین نمی‌کند.",
        "Sonuç geçmişinize kaydedilir. Gelecek olayları garanti etmeyen sembolik bir yorumdur.",
    )[index]
    return f'{name}\n\n{DETAILS[key][index]}\n\n{price}\n\n{ending}'
