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


def find_favorable_dates(event_type: str, from_date: date, count: int = 5,
                         to_date: date | None = None, weekdays: str = "all",
                         birth_date: date | None = None) -> list[dict]:
    """Rank symbolic dates inside the customer's real availability window."""
    if event_type not in FAVORABLE_ENERGIES or weekdays not in ("all", "workdays", "weekends"):
        raise ValueError("Unknown event or weekday preference")
    end = to_date or from_date + timedelta(days=60)
    favorable_nums = FAVORABLE_ENERGIES[event_type]
    candidates = []
    current = from_date + timedelta(days=1)
    while current <= end:
        if ((weekdays == "workdays" and current.weekday() >= 5)
                or (weekdays == "weekends" and current.weekday() < 5)):
            current += timedelta(days=1)
            continue
        energy = _day_energy(current)
        personal = _reduce(birth_date.day + birth_date.month + current.day + current.month
                           + sum(int(c) for c in str(current.year))) if birth_date else None
        score = int(energy in favorable_nums) + int(personal in favorable_nums)
        candidates.append({"date": current.strftime("%d.%m.%Y"), "weekday": current.weekday(),
                           "energy": energy, "personal_energy": personal, "date_obj": current, "score": score})
        current += timedelta(days=1)
    best = sorted(candidates, key=lambda item: (-item["score"], item["date_obj"]))[:count]
    return sorted(best, key=lambda item: item["date_obj"])
