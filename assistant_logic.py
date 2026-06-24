import re
from itertools import product
from typing import Any, Callable

from db import (
    CITY_FILTER_NAMES,
    get_cities,
    get_city_card,
    get_city_names,
    get_regions,
    get_top_cities,
)

DISTRICTS = {"ЦФО", "СЗФО", "ЮФО", "СКФО", "ПФО", "УФО", "СФО", "ДФО"}
DISTRICT_NAME_ALIASES = {
    "центральный федеральный округ": "ЦФО",
    "северо западный федеральный округ": "СЗФО",
    "южный федеральный округ": "ЮФО",
    "северо кавказский федеральный округ": "СКФО",
    "приволжский федеральный округ": "ПФО",
    "уральский федеральный округ": "УФО",
    "сибирский федеральный округ": "СФО",
    "дальневосточный федеральный округ": "ДФО",
}

DEFAULT_HELP = (
    "Я могу помочь с городами из локальной базы: показать список по округу, "
    "найти карточку города, вывести топ по населению. "
    "Например: «города ЦФО», «карточка Тверь», «топ 5 городов ПФО»."
)
OUT_OF_DOMAIN_REFUSAL = (
    "Я отвечаю только на вопросы по географии и локальной базе городов. "
    "Спросите про города, федеральные округа, население или рейтинги."
)
UNSUPPORTED_GEO_HELP = (
    "Я работаю с локальной SQLite-базой городов. "
    "Могу показать списки городов, карточку города из базы или топ по населению."
)
DOMAIN_HELP = (
    "Проект работает с локальной SQLite-базой городов. "
    "Доступны карточки городов, списки с фильтрами по федеральному округу "
    "и населению, а также топы по населению. "
    "Сейчас в базе есть округа: ЦФО, СЗФО, ЮФО, СКФО, ПФО, УФО, СФО и ДФО."
)

HELP_PHRASES = (
    "помощ", "помоги с город", "помоги разобраться с округ",
    "умеешь", "умеет", "справка", "help", "команды",
)
PROJECT_PHRASES = (
    "о проект",
    "про проект",
    "этот проект",
    "что в базе",
    "какие данные",
    "какие округа",
    "федеральные округа",
    "хранится в локальной базе",
    "в данных",
    "локальная база",
    "database",
    "dataset",
    "what data",
    "what is this project",
    "about this project",
)
GEO_PHRASES = (
    "географ",
    "geography",
    "город",
    "города",
    "city",
    "cities",
    "насел",
    "population",
    "бакет",
    "bucket",
    "kladr",
    "кладр",
    "source_key",
    "округ",
    "district",
    "регион",
    "region",
    "федеральн",
    "рейтинг город",
    "top cities",
    "biggest cities",
    "largest cities",
)
TOP_PHRASES = ("топ", "top", "рейтинг", "ranking", "самые", "крупн", "biggest", "largest")
LIST_PHRASES = ("город", "cities", "насел", "бакет", "bucket")
NEGATED_LIST_PHRASES = ("без списка", "не показывай список", "не выводи список")
OUT_OF_DOMAIN_PHRASES = ("погода", "weather")
RELATED_PHRASES = HELP_PHRASES + PROJECT_PHRASES + GEO_PHRASES

CITY_FILTER_ARGS = set(CITY_FILTER_NAMES)
TOOL_ARGUMENTS = {
    "find_cities": CITY_FILTER_ARGS | {"limit"},
    "get_city_card": {"name"},
    "get_top_cities": CITY_FILTER_ARGS | {"metric", "limit"},
}
TOOL_HANDLERS = {
    "find_cities": get_cities,
    "get_city_card": get_city_card,
    "get_top_cities": get_top_cities,
}
TOOL_ALIASES = {
    "get_cities": "find_cities",
    "city_card": "get_city_card",
    "get_city": "get_city_card",
    "top_cities": "get_top_cities",
}
ARG_ALIASES = {
    "district": "federal_district",
    "federal_region": "federal_district",
    "subject": "region",
    "area": "region",
    "city": "name",
    "city_name": "name",
    "city_group": "bucket",
    "group": "bucket",
    "title": "name",
    "top_n": "limit",
    "count": "limit",
    "max_count": "limit",
    "sort_by": "metric",
    "ranking": "metric",
}

KNOWN_BUCKETS = ("1м+", "500к-1м", "250к-500к", "100к-250к", "50к-100к", "до 50к")
LIMIT_PATTERNS = (
    r"(?:топ|top)\s*(\d[\d\s_]*)",
    r"(?:первые|покажи|выведи|найди|limit)\s+(\d[\d\s_]*)",
)
MAX_BOUND_OPERATORS = {"<=", "<", "меньше", "ниже", "до", "less", "under"}
BOUND_OPERATOR_PATTERN = r">=|>|<=|<|больше|выше|от|more|greater|меньше|ниже|до|less|under"
REGION_POPULATION_LABELS = {
    "region_population": ("region_population", "население региона", "население субъекта"),
    "region_city_population": ("region_city_population", "городское население региона"),
    "region_country_population": ("region_country_population", "сельское население региона"),
}
WORD_VARIANT_RULES = (
    (("ский",), 2, ("ого", "ому", "им", "ом")),
    (("ий",), 2, ("его", "ему", "им", "ем")),
    (("ый", "ой"), 2, ("ого", "ому", "ым", "ом")),
    (("ь",), 1, ("и", "ью")),
    (("а",), 1, ("ы", "е", "у", "ой")),
    (("я",), 1, ("и", "е", "ю", "ей")),
    (("й",), 1, ("я", "ю", "е", "ем")),
)


def has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def text_answer(answer: str) -> dict[str, str]:
    return {"mode": "text", "answer": answer.strip() or DEFAULT_HELP}


def normalize_search_text(text: str) -> str:
    text = text.casefold().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def phrase_in_text(phrase: str, normalized_text: str) -> bool:
    phrase = normalize_search_text(phrase)
    return bool(phrase) and f" {phrase} " in f" {normalized_text} "


def word_variants(word: str) -> set[str]:
    variants = {word}
    if len(word) < 3:
        return variants

    for endings, trim, suffixes in WORD_VARIANT_RULES:
        if word.endswith(endings):
            stem = word[:-trim]
            variants.update(f"{stem}{suffix}" for suffix in suffixes)
            return variants

    if word.endswith("ел"):
        variants.add(f"{word[:-2]}ле")
    if re.search(r"[бвгджзклмнпрстфхцчшщ]$", word):
        variants.update(f"{word}{suffix}" for suffix in ("а", "у", "е", "ом"))
    return variants


def city_name_variants(name: str) -> set[str]:
    words = normalize_search_text(name).split()
    if not words:
        return set()

    forms = [word_variants(word) for word in words]
    variants = {normalize_search_text(name)}
    variants.update(" ".join(parts) for parts in product(*forms))
    return variants


def extract_city_name(message: str) -> str | None:
    text = normalize_search_text(message)
    for name in get_city_names():
        if any(phrase_in_text(variant, text) for variant in city_name_variants(name)):
            return name
    return None


def extract_region(message: str) -> str | None:
    text = normalize_search_text(message)
    return next((region for region in get_regions() if phrase_in_text(region, text)), None)


def extract_district(message: str) -> str | None:
    upper_text = message.upper()
    if district := next((district for district in DISTRICTS if district in upper_text), None):
        return district

    text = normalize_search_text(message)
    return next(
        (
            district
            for district_name, district in DISTRICT_NAME_ALIASES.items()
            if any(
                phrase_in_text(variant, text)
                for variant in city_name_variants(district_name)
            )
        ),
        None,
    )


def normalize_bucket_value(value: str) -> str | None:
    value = re.sub(r"\s+", "", value.casefold().replace("–", "-").replace("—", "-"))
    value = value.replace("k", "к").replace("m", "м")
    if value in KNOWN_BUCKETS:
        return value
    if value.startswith("до"):
        return "до 50к" if re.sub(r"\D", "", value) == "50" else None

    match = re.fullmatch(r"(\d+)([км]?)-(\d+)([км]?)", value)
    if not match:
        return None
    left, left_unit, right, right_unit = match.groups()
    normalized = f"{left}{left_unit or 'к'}-{right}{right_unit or 'к'}"
    normalized = normalized.replace("1000к", "1м")
    return normalized if normalized in KNOWN_BUCKETS else None


def extract_bucket(message: str) -> str | None:
    text = message.casefold().replace("–", "-").replace("—", "-")
    for bucket in KNOWN_BUCKETS:
        if bucket in text:
            return bucket

    bucket_pattern = r"до\s*\d+\s*[кk]?|\d+\s*[кkмm]?\s*-\s*\d+\s*[кkмm]?|\d+\s*[мm]\+"
    match = re.search(
        rf"(?:бакет(?:е)?|bucket|групп[ае]?|категори[ия])\s*[:=]?\s*({bucket_pattern})",
        text,
    )
    if not match and has_any(text, ("город", "cities", "топ", "top")):
        match = re.search(rf"\b({bucket_pattern})\b", text)
    if not match:
        return None
    return normalize_bucket_value(match.group(1))


def extract_limit(message: str) -> int | None:
    for pattern in LIMIT_PATTERNS:
        match = re.search(pattern, message.casefold())
        if match:
            return int(re.sub(r"\D", "", match.group(1)))
    return None


def extract_bounds(message: str, labels_pattern: str) -> tuple[int | None, int | None]:
    match = re.search(
        rf"(?:{labels_pattern})[^0-9<>]*?({BOUND_OPERATOR_PATTERN})?\s*(\d[\d\s_]*)",
        message.casefold(),
    )
    if not match:
        return None, None
    value = int(re.sub(r"\D", "", match.group(2)))
    operator = (match.group(1) or "").strip()
    if operator in MAX_BOUND_OPERATORS:
        return None, value
    return value, None


BASE_FILTER_EXTRACTORS = (
    ("federal_district", extract_district),
    ("region", extract_region),
    ("bucket", extract_bucket),
)


def add_bounds(
    arguments: dict[str, Any],
    prefix: str,
    message: str,
    labels_pattern: str,
) -> None:
    for suffix, value in zip(("min", "max"), extract_bounds(message, labels_pattern)):
        if value is not None:
            arguments[f"{prefix}_{suffix}"] = value


def extract_common_filters(message: str) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        key: value
        for key, extractor in BASE_FILTER_EXTRACTORS
        if (value := extractor(message))
    }

    text = message.casefold()
    if not any(has_any(text, labels) for labels in REGION_POPULATION_LABELS.values()):
        add_bounds(arguments, "population", message, r"насел\w*|population|численн\w*")
    for prefix, labels in REGION_POPULATION_LABELS.items():
        if prefix == "region_population" and has_any(
            text,
            REGION_POPULATION_LABELS["region_city_population"]
            + REGION_POPULATION_LABELS["region_country_population"],
        ):
            continue
        label_pattern = "|".join(re.escape(label) for label in labels)
        add_bounds(arguments, prefix, message, label_pattern)

    match = re.search(r"\b(?:kladr|кладр)\s*[:=]?\s*(\d{6,})\b", text)
    if match:
        arguments["kladr"] = match.group(1)

    match = re.search(
        r"(?:source_key|ключ)\s*[:=]+\s*([^;]+)$",
        message,
        flags=re.IGNORECASE,
    )
    if match:
        arguments["source_key"] = match.group(1).strip()
    return arguments


def clean_tool_call(name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    name = TOOL_ALIASES.get(name.strip(), name.strip())
    args = {ARG_ALIASES.get(key, key): value for key, value in args.items()}
    if name == "find_cities" and "name" in args:
        name = "get_city_card"
    if name == "get_city_card" and "name" not in args and "query" in args:
        args["name"] = args["query"]
    allowed_args = TOOL_ARGUMENTS.get(name, set())
    return name, {key: value for key, value in args.items() if key in allowed_args}


def tool_choice(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"mode": "tool", "function_name": name, "arguments": args}


def make_answer(name: str, result: Any) -> str:
    if name == "get_city_card":
        return (
            "Город не найден в локальной базе."
            if result is None
            else f"Карточка города: {result['name']}."
        )
    return (
        f"Найдено городов: {len(result)}."
        if isinstance(result, list)
        else "Готово."
    )


def run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unsupported function: {name}")
    result = handler(**args)
    return {
        "mode": "tool",
        "answer": make_answer(name, result),
        "function_name": name,
        "arguments": args,
        "result": result,
    }


def run_choice(choice: Any) -> dict[str, Any] | None:
    if not isinstance(choice, dict):
        return None

    try:
        if choice.get("mode") == "text":
            answer = choice.get("answer")
            if not isinstance(answer, str):
                return None
            answer = answer.strip() or DEFAULT_HELP
            if not re.search(r"[А-Яа-яЁё]", answer):
                answer = UNSUPPORTED_GEO_HELP
            return text_answer(answer)

        if choice.get("mode") != "tool":
            return None

        name = choice.get("function_name")
        args = choice.get("arguments") or {}
        if not (isinstance(name, str) and name.strip() and isinstance(args, dict)):
            return None
        return run_tool(*clean_tool_call(name, args))
    except Exception:
        return None


def pick_local(message: str) -> dict[str, Any] | None:
    text = message.casefold()
    if has_any(text, HELP_PHRASES):
        return text_answer(DEFAULT_HELP)

    filters = extract_common_filters(message)
    if "source_key" in filters:
        return tool_choice("find_cities", {"source_key": filters["source_key"]})
    if "kladr" in filters:
        return tool_choice("find_cities", {"kladr": filters["kladr"]})

    city_name = extract_city_name(message)
    if city_name:
        return tool_choice("get_city_card", {"name": city_name})
    if has_any(text, PROJECT_PHRASES):
        return text_answer(DOMAIN_HELP)

    district = filters.get("federal_district")
    if has_any(text, TOP_PHRASES) and (district or has_any(text, GEO_PHRASES)):
        filters.update(metric="population", limit=extract_limit(message) or 5)
        return tool_choice("get_top_cities", filters)

    if not has_any(text, NEGATED_LIST_PHRASES) and (
        district or filters.get("region") or has_any(text, LIST_PHRASES)
    ):
        return tool_choice("find_cities", filters)
    return None


def looks_related(message: str) -> bool:
    text = message.casefold()
    return (
        has_any(text, RELATED_PHRASES)
        or extract_district(message) is not None
        or extract_city_name(message) is not None
    )


def build_assistant_response(
    message: str,
    choose_tool: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    user_message = message.strip()
    if not user_message:
        return text_answer(
            "Напишите вопрос, и я помогу с городами из локальной базы."
        )
    if has_any(user_message.casefold(), OUT_OF_DOMAIN_PHRASES):
        return text_answer(OUT_OF_DOMAIN_REFUSAL)

    if response := run_choice(pick_local(user_message)):
        return response

    if not looks_related(user_message):
        return text_answer(OUT_OF_DOMAIN_REFUSAL)

    try:
        response = run_choice(choose_tool(user_message))
    except Exception:
        response = None
    return response or text_answer(UNSUPPORTED_GEO_HELP)
