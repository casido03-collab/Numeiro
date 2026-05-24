"""Вспомогательные утилиты для business dialog."""
import re


def is_valid_date(text: str) -> bool:
    """Проверить что строка похожа на дату (дд.мм.гггг)."""
    return bool(re.match(r"^\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4}$", text.strip()))


def clean_name(text: str) -> str:
    """Взять первое слово и капитализировать."""
    parts = text.strip().split()
    return parts[0].capitalize() if parts else text
