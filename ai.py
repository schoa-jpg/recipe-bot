import os
import logging
import base64
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

log = logging.getLogger(__name__)

BASE_URL = "https://openai.api.proxyapi.ru/v1"


def _get_client():
    key = os.getenv("PROXY_API_KEY", "")
    if not key:
        return None
    return AsyncOpenAI(api_key=key, base_url=BASE_URL)

SYSTEM_PROMPT = """Ты — умный и полезный помощник. Отвечай на русском языке.
Если вопрос связан с кулинарией — давай подробные рецепты и советы.
Если вопрос общий — отвечай по существу, кратко и информативно.
Форматируй ответ удобно и чётко."""


async def ask_ai(prompt: str, model: str = "openai/gpt-4o-mini") -> str:
    client = _get_client()
    if not client:
        return "AI не настроен. Добавьте PROXY_API_KEY."
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
            temperature=0.7,
        )
        return resp.choices[0].message.content or "Нет ответа."
    except Exception as e:
        log.error(f"ask_ai error: {e}")
        return f"Ошибка AI: {e}"


async def analyze_image(image_url: str, prompt: str = "Что это за блюдо? Опиши подробно и дай рецепт приготовления.", model: str = "openai/gpt-4o-mini") -> str:
    client = _get_client()
    if not client:
        return "AI не настроен. Добавьте PROXY_API_KEY."
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
            max_tokens=1500,
            temperature=0.7,
        )
        return resp.choices[0].message.content or "Нет ответа."
    except Exception as e:
        log.error(f"analyze_image error: {e}")
        return f"Ошибка AI: {e}"
