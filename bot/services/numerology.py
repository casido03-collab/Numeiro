from datetime import date


def _reduce(n: int, master_numbers: tuple = (11, 22, 33)) -> int:
    """Reduce a number to single digit, preserving master numbers."""
    while n > 9 and n not in master_numbers:
        n = sum(int(d) for d in str(n))
    return n


def life_path_number(birth_date: date) -> int:
    """Calculate Life Path Number (число жизненного пути)."""
    day = _reduce(birth_date.day)
    month = _reduce(birth_date.month)
    year = _reduce(sum(int(d) for d in str(birth_date.year)))
    return _reduce(day + month + year)


def destiny_number(birth_date: date) -> int:
    """Calculate Destiny Number (число судьбы) — sum of all digits in full date."""
    digits = (
        [int(d) for d in str(birth_date.day).zfill(2)]
        + [int(d) for d in str(birth_date.month).zfill(2)]
        + [int(d) for d in str(birth_date.year)]
    )
    return _reduce(sum(digits))


def personality_number(birth_date: date) -> int:
    """Calculate Personality Number (число личности) — day of birth reduced."""
    return _reduce(birth_date.day)


def soul_number(birth_date: date) -> int:
    """Calculate Soul Urge Number — sum of month + year digits."""
    month_sum = sum(int(d) for d in str(birth_date.month).zfill(2))
    year_sum = sum(int(d) for d in str(birth_date.year))
    return _reduce(month_sum + year_sum)


def calculate_all(birth_date: date) -> dict:
    """Return all numerology numbers for a birth date."""
    return {
        "life_path": life_path_number(birth_date),
        "destiny": destiny_number(birth_date),
        "personality": personality_number(birth_date),
        "soul": soul_number(birth_date),
        "birth_day": birth_date.day,
        "birth_month": birth_date.month,
        "birth_year": birth_date.year,
    }


# Характеристики числа жизненного пути
LIFE_PATH_TRAITS: dict[int, dict] = {
    1: {
        "name": "Лидер",
        "strengths": ["независимость", "лидерство", "решительность", "новаторство"],
        "weaknesses": ["упрямство", "эгоцентризм", "нетерпимость"],
        "money": "Деньги приходят через собственные проекты и лидерские позиции",
        "relationships": "Нуждается в партнере, который уважает независимость",
        "purpose": "Прокладывать новые пути и вдохновлять других",
    },
    2: {
        "name": "Дипломат",
        "strengths": ["интуиция", "эмпатия", "сотрудничество", "терпение"],
        "weaknesses": ["нерешительность", "зависимость", "чрезмерная чувствительность"],
        "money": "Деньги приходят через партнерство и командную работу",
        "relationships": "Идеальный партнер, ценит гармонию и доверие",
        "purpose": "Создавать мир и баланс в отношениях",
    },
    3: {
        "name": "Творец",
        "strengths": ["творчество", "общительность", "оптимизм", "выразительность"],
        "weaknesses": ["рассеянность", "поверхностность", "избегание конфликтов"],
        "money": "Деньги приходят через творческие проекты и коммуникацию",
        "relationships": "Яркий и притягательный партнер, нуждается в свободе самовыражения",
        "purpose": "Вдохновлять через творчество и радость",
    },
    4: {
        "name": "Строитель",
        "strengths": ["трудолюбие", "надежность", "организованность", "практичность"],
        "weaknesses": ["жесткость", "консерватизм", "занудство"],
        "money": "Деньги приходят через усердный труд и системный подход",
        "relationships": "Верный и надежный партнер, ценит стабильность",
        "purpose": "Создавать прочные основы и воплощать мечты в реальность",
    },
    5: {
        "name": "Искатель",
        "strengths": ["адаптивность", "свобода", "авантюризм", "коммуникабельность"],
        "weaknesses": ["непостоянство", "безответственность", "импульсивность"],
        "money": "Деньги приходят через многообразие занятий и перемены",
        "relationships": "Нуждается в партнере, дающем свободу и разнообразие",
        "purpose": "Исследовать мир и расширять границы возможного",
    },
    6: {
        "name": "Хранитель",
        "strengths": ["забота", "ответственность", "гармония", "любовь"],
        "weaknesses": ["жертвенность", "контроль", "перфекционизм"],
        "money": "Деньги приходят через помощь другим и создание уюта",
        "relationships": "Преданный и заботливый партнер, ставит семью на первое место",
        "purpose": "Нести любовь и исцеление в мир",
    },
    7: {
        "name": "Мудрец",
        "strengths": ["аналитическое мышление", "духовность", "интуиция", "глубина"],
        "weaknesses": ["замкнутость", "скептицизм", "одиночество"],
        "money": "Деньги приходят через знания, экспертизу и анализ",
        "relationships": "Требует глубокой духовной связи, избегает поверхностного",
        "purpose": "Познавать истину и делиться мудростью",
    },
    8: {
        "name": "Властитель",
        "strengths": ["амбициозность", "деловая хватка", "власть", "стойкость"],
        "weaknesses": ["материализм", "властолюбие", "жесткость"],
        "money": "Деньги — стихия восьмерки, природный магнит достатка",
        "relationships": "Нуждается в равном партнере, уважающем амбиции",
        "purpose": "Достигать успеха и использовать власть во благо",
    },
    9: {
        "name": "Гуманист",
        "strengths": ["сострадание", "широта взглядов", "мудрость", "альтруизм"],
        "weaknesses": ["мечтательность", "разочарование", "жертвенность"],
        "money": "Деньги приходят через служение большим идеям",
        "relationships": "Любит всё человечество, ищет глубокую душевную связь",
        "purpose": "Служить человечеству и завершать кармические циклы",
    },
    11: {
        "name": "Просветленный",
        "strengths": ["интуиция", "вдохновение", "духовная чувствительность", "харизма"],
        "weaknesses": ["тревожность", "идеализм", "нервозность"],
        "money": "Деньги приходят через духовную работу и вдохновение других",
        "relationships": "Глубокие духовные связи, сложно в обычных отношениях",
        "purpose": "Нести свет и пробуждать духовность в мире",
    },
    22: {
        "name": "Мастер-строитель",
        "strengths": ["грандиозное видение", "практическая мудрость", "лидерство", "созидание"],
        "weaknesses": ["давление ответственности", "перфекционизм", "страх провала"],
        "money": "Деньги через масштабные проекты, меняющие мир",
        "relationships": "Нуждается в поддерживающем партнере с общими ценностями",
        "purpose": "Воплощать великие идеи на благо человечества",
    },
    33: {
        "name": "Мастер-учитель",
        "strengths": ["безусловная любовь", "мудрость", "исцеление", "вдохновение"],
        "weaknesses": ["самопожертвование", "несение чужой боли", "идеализм"],
        "money": "Деньги через исцеление и духовное служение",
        "relationships": "Любовь к человечеству, глубокие кармические связи",
        "purpose": "Нести безусловную любовь и исцелять мир",
    },
}


def get_traits(number: int) -> dict:
    return LIFE_PATH_TRAITS.get(number, LIFE_PATH_TRAITS[1])
