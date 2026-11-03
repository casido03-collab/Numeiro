"""Native VK keyboards. VK supports four semantic colors, not custom hex colors."""
import json

ICONS = {"personal_question": "🔮", "mini_reading": "✨", "tarot_card": "🃏",
         "full_matrix": "🌌", "compatibility": "💞", "weekly_report": "🌙", "date_selection": "📆"}
SHORT_NAMES = {"personal_question": "Личный вопрос", "mini_reading": "Мини-разбор", "tarot_card": "Карта дня",
               "full_matrix": "Матрица судьбы", "compatibility": "Совместимость", "weekly_report": "Неделя", "date_selection": "Подбор дат"}
ORDER = list(SHORT_NAMES)
CATALOG_PAGES = (
    ("personal_question", "mini_reading", "tarot_card", "weekly_report"),
    ("full_matrix", "compatibility", "date_selection", "vip"),
)
CATALOG_LABELS = {"personal_question": "Вопрос", "mini_reading": "Мини", "tarot_card": "Карта",
                  "weekly_report": "Неделя", "full_matrix": "Матрица", "compatibility": "Пара",
                  "date_selection": "Даты", "vip": "VIP"}


def button(label, command, color="primary"):
    return {"action": {"type": "text", "label": label[:40],
                       "payload": json.dumps({"a": command}, ensure_ascii=False)}, "color": color}


def link(label, url):
    return {"action": {"type": "open_link", "label": label[:40], "link": url}}


def keyboard(rows, inline=True):
    assert len(rows) <= (6 if inline else 10)
    assert all(1 <= len(row) <= 4 for row in rows)
    assert not inline or sum(map(len, rows)) <= 10
    return {"one_time": False, "inline": inline, "buttons": rows}


def home():
    return keyboard([
        [button("🔮 Услуги", "catalog"), button("🌙 Бесплатно", "free", "positive")],
        [button("📚 Мои разборы", "history"), button("💎 VIP", "vip")],
        [button("👤 Профиль", "profile", "secondary"), button("💜 Техподдержка", "support", "secondary")],
        [button("📖 Интересное", "learn", "secondary"), button("👥 Друзья", "friends", "secondary")],
    ], inline=False)


def catalog(page=0):
    page = max(0, min(page, len(CATALOG_PAGES)-1))
    buttons = []
    for product in CATALOG_PAGES[page]:
        command = "vip" if product == "vip" else f"product:{product}"
        icon = "💎" if product == "vip" else ICONS[product]
        # Keep mobile labels short; details and price are inside each offer.
        buttons.append(button(f"{icon} {CATALOG_LABELS[product]}", command))
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    rows.append([button("Ещё услуги →", "catalog:1", "secondary")] if page == 0
                else [button("← Назад", "catalog:0", "secondary")])
    rows.append([button("🌙 Бесплатно", "free", "positive"), button("Поддержка", "support", "secondary")])
    return keyboard(rows)


def back():
    return keyboard([[button("🔮 Главное меню", "menu", "secondary")]])


def choices(items, prefix, page=0, page_size=6):
    items = list(items)
    page = max(0, min(page, max(0, (len(items)-1)//page_size)))
    visible = items[page*page_size:(page+1)*page_size]
    buttons = [button(label, f"{prefix}:{key}") for key, label in visible]
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    nav = []
    if page:
        nav.append(button("← Назад", f"page:{prefix}:{page-1}", "secondary"))
    if (page+1)*page_size < len(items):
        nav.append(button("Ещё →", f"page:{prefix}:{page+1}", "secondary"))
    if nav:
        rows.append(nav)
    rows.append([button("🔮 Главное меню", "menu", "secondary")])
    return keyboard(rows)


LABEL_COMMANDS = {b["action"]["label"]: json.loads(b["action"]["payload"])["a"]
                  for row in home()["buttons"] for b in row}
