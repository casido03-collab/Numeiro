"""
Матрица судьбы — расчёт по методу Натальи Ладини.
Числа 1–22 (арканы таро).
"""
from datetime import date


def _reduce_to_22(n: int) -> int:
    """Reduce number keeping range 1–22."""
    while n > 22:
        n = sum(int(d) for d in str(n))
    if n == 0:
        n = 22
    return n


def calculate_matrix(birth_date: date) -> dict:
    """Calculate Destiny Matrix (Матрица судьбы) for a birth date."""
    d = birth_date.day
    m = birth_date.month
    y = birth_date.year

    # Основные числа
    d_r = _reduce_to_22(d)
    m_r = _reduce_to_22(m)
    y_r = _reduce_to_22(sum(int(c) for c in str(y)))
    total = _reduce_to_22(d_r + m_r + y_r)

    # Центр матрицы — личная сила
    personal_energy = _reduce_to_22(d_r + m_r)
    karmic_tail = _reduce_to_22(d_r + total)
    karma_task = _reduce_to_22(m_r + total)
    social_role = _reduce_to_22(personal_energy + total)

    # Линия неба (духовные задачи)
    sky_left = _reduce_to_22(d_r + personal_energy)
    sky_right = _reduce_to_22(m_r + personal_energy)
    sky_center = _reduce_to_22(sky_left + sky_right)

    # Линия земли (материальные задачи)
    earth_left = _reduce_to_22(d_r + karmic_tail)
    earth_right = _reduce_to_22(m_r + karma_task)
    earth_center = _reduce_to_22(earth_left + earth_right)

    # Зоны
    money_energy = _reduce_to_22(y_r + total)
    love_energy = _reduce_to_22(d_r + y_r)
    talent_energy = _reduce_to_22(m_r + y_r)

    return {
        "day": d_r,
        "month": m_r,
        "year": y_r,
        "total": total,
        "personal_energy": personal_energy,
        "karmic_tail": karmic_tail,
        "karma_task": karma_task,
        "social_role": social_role,
        "sky_left": sky_left,
        "sky_right": sky_right,
        "sky_center": sky_center,
        "earth_left": earth_left,
        "earth_right": earth_right,
        "earth_center": earth_center,
        "money_energy": money_energy,
        "love_energy": love_energy,
        "talent_energy": talent_energy,
    }


# Значения арканов
ARCANA: dict[int, dict] = {
    1: {"name": "Маг", "keywords": ["воля", "действие", "новые начала", "мастерство"]},
    2: {"name": "Жрица", "keywords": ["интуиция", "тайное знание", "пассивность", "ожидание"]},
    3: {"name": "Императрица", "keywords": ["плодородие", "творчество", "изобилие", "природа"]},
    4: {"name": "Император", "keywords": ["власть", "стабильность", "структура", "отец"]},
    5: {"name": "Иерофант", "keywords": ["духовность", "традиции", "обучение", "мудрость"]},
    6: {"name": "Влюбленные", "keywords": ["выбор", "союз", "любовь", "гармония"]},
    7: {"name": "Колесница", "keywords": ["победа", "движение", "воля", "контроль"]},
    8: {"name": "Сила", "keywords": ["сила духа", "выносливость", "смелость", "укрощение"]},
    9: {"name": "Отшельник", "keywords": ["мудрость", "одиночество", "поиск", "путь внутрь"]},
    10: {"name": "Колесо Фортуны", "keywords": ["удача", "перемены", "цикличность", "судьба"]},
    11: {"name": "Справедливость", "keywords": ["баланс", "правда", "карма", "закон"]},
    12: {"name": "Повешенный", "keywords": ["жертва", "переосмысление", "пауза", "трансформация"]},
    13: {"name": "Смерть", "keywords": ["трансформация", "конец", "обновление", "переход"]},
    14: {"name": "Умеренность", "keywords": ["баланс", "терпение", "интеграция", "исцеление"]},
    15: {"name": "Дьявол", "keywords": ["привязанность", "материализм", "иллюзии", "тень"]},
    16: {"name": "Башня", "keywords": ["внезапные перемены", "разрушение", "откровение", "кризис"]},
    17: {"name": "Звезда", "keywords": ["надежда", "вдохновение", "обновление", "вера"]},
    18: {"name": "Луна", "keywords": ["интуиция", "страхи", "подсознание", "иллюзии"]},
    19: {"name": "Солнце", "keywords": ["успех", "радость", "ясность", "жизненная сила"]},
    20: {"name": "Суд", "keywords": ["пробуждение", "трансформация", "призыв", "обновление"]},
    21: {"name": "Мир", "keywords": ["завершение", "целостность", "успех", "интеграция"]},
    22: {"name": "Шут", "keywords": ["начало пути", "свобода", "доверие", "потенциал"]},
}


def get_arcana_info(number: int) -> dict:
    return ARCANA.get(number, ARCANA[1])


def matrix_to_context(matrix: dict) -> dict:
    """Convert raw matrix numbers to enriched context for AI."""
    return {
        "personal_energy": {
            "number": matrix["personal_energy"],
            "arcana": get_arcana_info(matrix["personal_energy"]),
        },
        "karma_task": {
            "number": matrix["karma_task"],
            "arcana": get_arcana_info(matrix["karma_task"]),
        },
        "karmic_tail": {
            "number": matrix["karmic_tail"],
            "arcana": get_arcana_info(matrix["karmic_tail"]),
        },
        "social_role": {
            "number": matrix["social_role"],
            "arcana": get_arcana_info(matrix["social_role"]),
        },
        "money_energy": {
            "number": matrix["money_energy"],
            "arcana": get_arcana_info(matrix["money_energy"]),
        },
        "love_energy": {
            "number": matrix["love_energy"],
            "arcana": get_arcana_info(matrix["love_energy"]),
        },
        "talent_energy": {
            "number": matrix["talent_energy"],
            "arcana": get_arcana_info(matrix["talent_energy"]),
        },
        "sky_center": {
            "number": matrix["sky_center"],
            "arcana": get_arcana_info(matrix["sky_center"]),
        },
        "earth_center": {
            "number": matrix["earth_center"],
            "arcana": get_arcana_info(matrix["earth_center"]),
        },
    }
