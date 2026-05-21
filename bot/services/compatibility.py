"""Совместимость двух людей — кодовый расчёт."""
from datetime import date
from .numerology import life_path_number, destiny_number, personality_number


COMPATIBILITY_MATRIX: dict[tuple[int, int], int] = {}

_BASE_COMPAT = {
    (1, 1): 65, (1, 2): 72, (1, 3): 85, (1, 4): 60, (1, 5): 78,
    (1, 6): 70, (1, 7): 55, (1, 8): 80, (1, 9): 68,
    (2, 2): 75, (2, 3): 80, (2, 4): 70, (2, 5): 65, (2, 6): 90,
    (2, 7): 72, (2, 8): 60, (2, 9): 85,
    (3, 3): 70, (3, 4): 65, (3, 5): 88, (3, 6): 75, (3, 7): 60,
    (3, 8): 72, (3, 9): 82,
    (4, 4): 68, (4, 5): 55, (4, 6): 80, (4, 7): 75, (4, 8): 85,
    (4, 9): 65,
    (5, 5): 72, (5, 6): 65, (5, 7): 70, (5, 8): 75, (5, 9): 80,
    (6, 6): 85, (6, 7): 68, (6, 8): 70, (6, 9): 90,
    (7, 7): 62, (7, 8): 65, (7, 9): 75,
    (8, 8): 78, (8, 9): 70,
    (9, 9): 80,
}


def _compat_score(n1: int, n2: int) -> int:
    """Get base compatibility score for two life-path numbers."""
    key = (min(n1, n2), max(n1, n2))
    if n1 > 9:
        n1 = n1 % 9 or 9
    if n2 > 9:
        n2 = n2 % 9 or 9
    key = (min(n1, n2), max(n1, n2))
    return _BASE_COMPAT.get(key, 70)


def calculate_compatibility(birth1: date, birth2: date, relation_type: str) -> dict:
    """Calculate full compatibility between two people."""
    lp1 = life_path_number(birth1)
    lp2 = life_path_number(birth2)
    d1 = destiny_number(birth1)
    d2 = destiny_number(birth2)
    p1 = personality_number(birth1)
    p2 = personality_number(birth2)

    base = _compat_score(lp1, lp2)
    emotional = _compat_score(d1, d2)
    everyday = _compat_score(p1, p2)

    relation_bonuses = {
        "love": 0,
        "marriage": -3,
        "friendship": +5,
        "work": +3,
        "ex": -8,
        "potential": +2,
    }
    bonus = relation_bonuses.get(relation_type, 0)

    overall = min(99, max(1, int((base * 0.5 + emotional * 0.3 + everyday * 0.2) + bonus)))

    # Конфликтные зоны
    conflict_score = abs(lp1 - lp2)
    conflict_level = "низкий" if conflict_score <= 2 else ("средний" if conflict_score <= 5 else "высокий")

    # Союзные числа (1+8, 2+6, 3+5, 4+4, 7+9)
    harmonious_pairs = {(1, 8), (2, 6), (3, 5), (4, 4), (7, 9)}
    lp_pair = (min(lp1, lp2), max(lp1, lp2))
    is_harmonious = lp_pair in harmonious_pairs

    return {
        "overall_percent": overall,
        "emotional_score": emotional,
        "everyday_score": everyday,
        "conflict_level": conflict_level,
        "is_harmonious_pair": is_harmonious,
        "life_path_1": lp1,
        "life_path_2": lp2,
        "destiny_1": d1,
        "destiny_2": d2,
        "personality_1": p1,
        "personality_2": p2,
        "relation_type": relation_type,
    }
