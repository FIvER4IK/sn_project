import os
import uuid
import warnings
from typing import Any

import requests
from db import CITY_FILTER_NAMES
from dotenv import load_dotenv
from urllib3.exceptions import InsecureRequestWarning

load_dotenv()

AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
BASE_URL = "https://gigachat.devices.sberbank.ru/api/v1"
CHAT_URL = f"{BASE_URL}/chat/completions"
DEFAULT_SCOPE = "GIGACHAT_API_PERS"
MODEL_NAME = "GigaChat-2"
CITY_FILTER_TOOL_PROPERTIES = {
    name: {"type": "integer" if name.endswith(("_min", "_max")) else "string"}
    for name in CITY_FILTER_NAMES
}

SYSTEM_PROMPT = """
Ты русскоязычный ассистент по географии с доступом к небольшой базе городов.
Всегда отвечай только на русском языке.
В первую очередь выбирай один из доступных инструментов, если запрос можно связать
с локальной базой городов.
Используй find_cities для списков городов и фильтров.
Используй get_city_card для карточки одного города по названию.
Используй get_top_cities для рейтингов, топов и крупнейших городов.
Если в запросе к топу указан федеральный округ, передай federal_district.
Если указан субъект РФ, передай region.
Если указан bucket/бакет или диапазон вроде 250к-500к, передай bucket.
Если указан фильтр населения, передай population_min или population_max.
Если указан КЛАДР, передай kladr. Если указан source_key, передай source_key.
Для фильтров region_population, region_city_population и region_country_population
используй соответствующие *_min или *_max аргументы.
Если пользователь просит крупнейшие города, используй metric=population.
Если limit не указан, предпочитай 5.
Не выдумывай неподдерживаемые операции и данные вне базы.
Если запрос не касается географии, городов, округов, населения или этой базы,
откажи на русском языке.
Если географический запрос нельзя уверенно сопоставить с инструментом, дай краткий
русский ответ о том, что доступна только локальная база городов.
""".strip()

FUNCTIONS = [
    {
        "name": "find_cities",
        "description": "Find cities using optional filters.",
        "parameters": {
            "type": "object",
            "properties": {
                **CITY_FILTER_TOOL_PROPERTIES,
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_city_card",
        "description": "Get a detailed card for one city by name.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "get_top_cities",
        "description": "Get top cities ranked by population.",
        "parameters": {
            "type": "object",
            "properties": {
                **CITY_FILTER_TOOL_PROPERTIES,
                "metric": {
                    "type": "string",
                    "enum": ["population"],
                },
                "limit": {"type": "integer"},
            },
            "required": ["metric"],
        },
    },
]


class GigaChatError(Exception):
    pass


def send_post(url: str, failure_message: str, **kwargs: Any) -> requests.Response:
    try:
        return requests.post(url, timeout=30, **kwargs)
    except Exception as exc:
        raise GigaChatError(f"{failure_message}: {exc}") from exc


def check_status(response: requests.Response, context: str) -> None:
    if response.status_code >= 400:
        raise GigaChatError(
            f"{context} error {response.status_code}: {response.text}"
        )


def read_json(response: requests.Response, context: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise GigaChatError(f"{context} returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise GigaChatError(f"{context} returned an unexpected response shape.")
    return payload


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not str(value).strip():
        raise GigaChatError(f"Missing environment variable: {name}")
    return str(value).strip()


def clean_auth_header(raw_key: str) -> str:
    if raw_key.startswith("Basic ") or raw_key.startswith("Bearer "):
        return raw_key
    return f"Basic {raw_key}"


def should_verify_ssl() -> bool:
    value = os.getenv("GIGACHAT_VERIFY_SSL", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def hide_ssl_warning_if_needed(verify_ssl: bool) -> None:
    if not verify_ssl:
        warnings.simplefilter("ignore", InsecureRequestWarning)


def function_call_choice(function_call: Any) -> dict[str, Any] | None:
    if not function_call:
        return None
    if not isinstance(function_call, dict):
        raise GigaChatError("GigaChat returned an invalid function_call.")

    function_name = function_call.get("name")
    if not isinstance(function_name, str) or not function_name.strip():
        raise GigaChatError("GigaChat returned a function call without a name.")

    arguments = function_call.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise GigaChatError("GigaChat returned non-object function arguments.")

    return {
        "mode": "tool",
        "function_name": function_name,
        "arguments": arguments,
    }


def obtain_access_token() -> str:
    auth_header = clean_auth_header(get_env("GIGACHAT_AUTH_KEY"))
    scope = os.getenv("GIGACHAT_SCOPE", DEFAULT_SCOPE)
    verify_ssl = should_verify_ssl()
    hide_ssl_warning_if_needed(verify_ssl)

    response = send_post(
        AUTH_URL,
        "Failed to obtain GigaChat token",
        data={"scope": scope},
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "RqUID": str(uuid.uuid4()),
            "Authorization": auth_header,
        },
        verify=verify_ssl,
    )
    check_status(response, "GigaChat OAuth")
    payload = read_json(response, "GigaChat OAuth")

    access_token = payload.get("access_token")
    if not access_token:
        raise GigaChatError("GigaChat OAuth response did not include access_token.")
    return access_token


def choose_tool(message: str) -> dict[str, Any]:
    access_token = obtain_access_token()
    verify_ssl = should_verify_ssl()
    hide_ssl_warning_if_needed(verify_ssl)

    response = send_post(
        CHAT_URL,
        "Failed to communicate with GigaChat",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={
            "model": MODEL_NAME,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            "functions": FUNCTIONS,
        },
        verify=verify_ssl,
    )
    check_status(response, "GigaChat chat")
    completion = read_json(response, "GigaChat chat")

    choices = completion.get("choices") or []
    if not isinstance(choices, list) or not choices:
        raise GigaChatError("GigaChat chat response did not include choices.")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise GigaChatError("GigaChat chat returned an invalid choice.")

    message_obj = first_choice.get("message", {})
    if not isinstance(message_obj, dict):
        raise GigaChatError("GigaChat chat returned an invalid message.")

    function_selection = function_call_choice(message_obj.get("function_call"))
    if function_selection is not None:
        return function_selection

    content = message_obj.get("content")
    if not isinstance(content, str) or not content.strip():
        content = "Не удалось выбрать поддерживаемую операцию."
    return {"mode": "text", "answer": content}
