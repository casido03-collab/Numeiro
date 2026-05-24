"""Валидация пользовательских данных в бизнес-диалоге."""
import re
from datetime import date, datetime


# ─── Имя ──────────────────────────────────────────────────────────────────────

_NAME_RE = re.compile(r"^[а-яёА-ЯЁa-zA-Z][а-яёА-ЯЁa-zA-Z\s\-]{1,29}$")

# Паттерны мусора: 3+ одинаковых символа подряд, клавиатурный спам
_JUNK_RE   = re.compile(r"(.)\1{2,}")                        # ааааа, 111, ...
_QWERTY_RE = re.compile(r"(qwert|asdf|zxcv|йцукен|фыва|ячсм)", re.I)


def validate_name(text: str) -> tuple[bool, str]:
    """
    Возвращает (ok, clean_name | error_key).
    error_key: 'too_short' | 'invalid_chars' | 'junk' | 'too_long'
    """
    name = text.strip().split()[0] if text.strip() else ""
    name = name.capitalize()

    if len(name) < 2:
        return False, "too_short"
    if len(name) > 30:
        return False, "too_long"
    if not _NAME_RE.match(name):
        return False, "invalid_chars"
    if _JUNK_RE.search(name) or _QWERTY_RE.search(name):
        return False, "junk"
    return True, name


NAME_ERRORS = {
    "too_short":     "Напишите своё настоящее имя — хотя бы два символа ✨",
    "too_long":      "Кажется, имя слишком длинное — напишите только имя, без фамилии 🌙",
    "invalid_chars": "В имени могут быть только буквы — напишите ещё раз 💫",
    "junk":          "Это не похоже на имя, душа моя 🌙 Напишите, как вас зовут?",
}


# ─── Дата рождения ─────────────────────────────────────────────────────────────

def validate_birth_date(text: str) -> tuple[bool, str]:
    """
    Возвращает (ok, 'ДД.ММ.ГГГГ' | error_key).
    error_key: 'format' | 'invalid_date' | 'too_young' | 'too_old' | 'future'
    """
    text = text.strip()

    # Пробуем распознать дату — принимаем несколько форматов
    dt = None
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d %m %Y"):
        try:
            dt = datetime.strptime(text, fmt).date()
            break
        except ValueError:
            continue

    # Попытка угадать если написали частично: "15 03 1990", "15031990"
    if dt is None:
        digits = re.sub(r"\D", "", text)
        if len(digits) == 8:
            try:
                dt = datetime.strptime(digits, "%d%m%Y").date()
            except ValueError:
                pass

    if dt is None:
        return False, "format"

    today = date.today()
    age   = (today - dt).days // 365

    if dt > today:
        return False, "future"
    if age < 10:
        return False, "too_young"
    if age > 100:
        return False, "too_old"

    return True, dt.strftime("%d.%m.%Y")


BIRTH_DATE_ERRORS = {
    "format":      "Напишите дату рождения вот так: 15.03.1990 ✨",
    "invalid_date": "Такой даты не существует — проверьте и напишите ещё раз 🌙",
    "future":      "Дата рождения не может быть в будущем 💫 Напишите правильную дату.",
    "too_young":   "Я работаю только со взрослыми людьми, душа моя 🌙",
    "too_old":     "Проверьте год рождения — кажется, там опечатка ✨",
}


# ─── Город ────────────────────────────────────────────────────────────────────

_CITY_RE = re.compile(r"^[а-яёА-ЯЁa-zA-Z][а-яёА-ЯЁa-zA-Z\s\-\.]{1,49}$")


def validate_city(text: str) -> tuple[bool, str]:
    """
    Возвращает (ok, clean_city | error_key).
    error_key: 'too_short' | 'invalid_chars' | 'junk'
    """
    city = text.strip()

    if len(city) < 2:
        return False, "too_short"
    if len(city) > 50:
        # Скорее всего написал что-то лишнее — берём первое слово
        city = city.split()[0]
    if not _CITY_RE.match(city):
        return False, "invalid_chars"
    if _JUNK_RE.search(city) or _QWERTY_RE.search(city):
        return False, "junk"

    return True, city.capitalize()


CITY_ERRORS = {
    "too_short":     "Напишите название города — хотя бы два символа 🌙",
    "invalid_chars": "В названии города могут быть только буквы — напишите ещё раз ✨",
    "junk":          "Это не похоже на город, душа моя 💫 Напишите где вы живёте?",
}
