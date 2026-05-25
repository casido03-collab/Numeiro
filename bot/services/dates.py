"""Подбор благоприятных дат."""
from datetime import date, timedelta
from .numerology import _reduce


def _day_energy(d: date) -> int:
    """Calculate energy number for a specific date."""
    return _reduce(d.day + d.month + sum(int(c) for c in str(d.year)))


FAVORABLE_ENERGIES = {
    "project_launch":      [1, 3, 5, 8],
    "wedding":             [2, 6, 9],
    "purchase":            [4, 6, 8],
    "move":                [3, 5, 1],
    "conversation":        [2, 3, 6],
    "travel":              [3, 5, 7],
    "interview":           [1, 3, 8],
    # Новые события
    "business_meeting":    [1, 3, 6, 8],
    "contract":            [4, 6, 8],
    "education":           [3, 5, 7],
    "investment":          [1, 4, 8],
    "medical":             [2, 6, 9],
    "creative":            [3, 5, 6],
    "spiritual":           [7, 9, 3],
}

EVENT_NAMES = {
    "project_launch":   "запуск проекта",
    "wedding":          "свадьба",
    "purchase":         "важная покупка",
    "move":             "переезд",
    "conversation":     "важный разговор",
    "travel":           "поездка",
    "interview":        "собеседование",
    # Новые события
    "business_meeting": "деловая встреча",
    "contract":         "подписание договора",
    "education":        "начало обучения",
    "investment":       "крупная инвестиция",
    "medical":          "медицинская процедура",
    "creative":         "творческий проект",
    "spiritual":        "духовная практика",
}


def find_favorable_dates(event_type: str, from_date: date, count: int = 5) -> list[dict]:
    """Find next N favorable dates for an event type."""
    favorable_nums = FAVORABLE_ENERGIES.get(event_type, [1, 3, 6])
    results = []
    current = from_date + timedelta(days=1)
    checked = 0

    while len(results) < count and checked < 60:
        energy = _day_energy(current)
        if energy in favorable_nums:
            weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            results.append({
                "date": current.strftime("%d.%m.%Y"),
                "weekday": weekday_names[current.weekday()],
                "energy": energy,
                "date_obj": current,
            })
        current += timedelta(days=1)
        checked += 1

    return results
