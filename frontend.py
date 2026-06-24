import os
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
EXAMPLE_QUERIES = [
    "покажи города ЦФО",
    "города ЦФО с населением больше 300000",
    "карточка Тверь",
    "топ 5 крупнейших городов",
    "города ПФО население > 1000000",
]


def get_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text
    if isinstance(payload, dict):
        return str(payload.get("detail", response.text))
    return response.text


def call_backend(message: str) -> dict[str, Any]:
    response = requests.post(
        f"{BACKEND_URL}/assistant",
        json={"message": message},
        timeout=60,
    )
    if response.status_code >= 400:
        raise RuntimeError(get_error_detail(response))
    return response.json()


def render_result(result: object) -> None:
    if result is None or result == []:
        st.info("По этому запросу данных не найдено.")
    elif isinstance(result, dict):
        st.dataframe([result], width="stretch")
    elif isinstance(result, list):
        st.dataframe(result, width="stretch")
    else:
        st.write(result)


def render_assistant_response(payload: dict[str, Any]) -> None:
    st.markdown(payload.get("answer", "Готово."))
    if payload.get("mode") == "tool":
        render_result(payload.get("result"))


def render_chat_entry(entry: dict[str, Any]) -> None:
    role = entry["role"]
    content = entry["content"]
    with st.chat_message(role):
        if role == "assistant" and isinstance(content, dict):
            render_assistant_response(content)
        else:
            st.markdown(content)


def add_message(role: str, content: object) -> dict[str, Any]:
    entry = {"role": role, "content": content}
    st.session_state.messages.append(entry)
    return entry


def render_sidebar() -> None:
    with st.sidebar:
        st.subheader("Примеры запросов")
        for example in EXAMPLE_QUERIES:
            st.code(example, language=None)
        st.markdown(f"Backend: `{BACKEND_URL}`")


def handle_prompt(prompt: str) -> None:
    render_chat_entry(add_message("user", prompt))

    with st.chat_message("assistant"):
        try:
            with st.spinner("Думаю..."):
                payload = call_backend(prompt)
            render_assistant_response(payload)
            assistant_content = payload
        except Exception as exc:
            error_message = f"Запрос не выполнен: {exc}"
            st.error(error_message)
            assistant_content = error_message
        add_message("assistant", assistant_content)


def main() -> None:
    st.set_page_config(page_title="Городской ассистент MVP", page_icon="🏙️", layout="wide")
    st.title("Городской ассистент MVP")
    st.caption("Задайте вопрос о городах, округах, населении, рейтингах и карточках из локальной SQLite-базы.")

    render_sidebar()

    st.session_state.setdefault("messages", [])
    for entry in st.session_state.messages:
        render_chat_entry(entry)

    prompt = st.chat_input("Спросите о городах...")
    if prompt:
        handle_prompt(prompt)


if __name__ == "__main__":
    main()
