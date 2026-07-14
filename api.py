import logging
import aiohttp
from deep_translator import GoogleTranslator

log = logging.getLogger(__name__)

BASE_URL = "https://www.themealdb.com/api/json/v1/1"

_en_ru = GoogleTranslator(source="en", target="ru")
_ru_en = GoogleTranslator(source="ru", target="en")


def _tr(text: str, direction: str = "en->ru") -> str:
    if not text or not str(text).strip():
        return text or ""
    try:
        tr = _en_ru if direction == "en->ru" else _ru_en
        return tr.translate(str(text))
    except Exception as e:
        log.error(f"translate error: {e}")
        return text


def _chunk_text(text: str, max_len: int = 4500) -> list[str]:
    if not text:
        return [""]
    if len(text) <= max_len:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            if current:
                chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def translate_meal_sync(meal: dict) -> dict:
    all_texts = [
        meal.get("strMeal") or "",
        meal.get("strCategory") or "",
        meal.get("strArea") or "",
        meal.get("strInstructions") or "",
    ]
    for i in range(1, 21):
        name = meal.get(f"strIngredient{i}") or ""
        if name.strip():
            all_texts.append(name.strip())

    all_translated = []
    for text in all_texts:
        chunks = _chunk_text(text)
        translated_chunks = []
        for chunk in chunks:
            result = _tr(chunk, "en->ru")
            translated_chunks.append(result)
        all_translated.append("\n".join(translated_chunks))

    translated = dict(meal)
    translated["strMeal"] = all_translated[0]
    translated["strCategory"] = all_translated[1]
    translated["strArea"] = all_translated[2]
    translated["strInstructions"] = all_translated[3]

    ing_idx = 0
    for i in range(1, 21):
        name = meal.get(f"strIngredient{i}", "")
        if name and name.strip():
            translated[f"strIngredient{i}"] = all_translated[4 + ing_idx]
            ing_idx += 1

    return translated


async def search_meals(name: str) -> list[dict]:
    en_name = _tr(name, "ru->en")
    log.info(f"search_meals: '{name}' -> '{en_name}'")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/search.php", params={"s": en_name}) as resp:
            data = await resp.json()
            meals = data.get("meals") or []
            log.info(f"search_meals: {len(meals)} results for '{en_name}'")
            return meals


async def search_by_ingredient(ingredient: str) -> list[dict]:
    en_ingredient = _tr(ingredient, "ru->en")
    log.info(f"search_by_ingredient: '{ingredient}' -> '{en_ingredient}'")
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{BASE_URL}/filter.php", params={"i": en_ingredient}
        ) as resp:
            data = await resp.json()
            return data.get("meals") or []


async def get_meal_by_id(meal_id: str) -> dict | None:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{BASE_URL}/lookup.php", params={"i": meal_id}
        ) as resp:
            data = await resp.json()
            meals = data.get("meals")
            return meals[0] if meals else None


async def get_random_meal() -> dict | None:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/random.php") as resp:
            data = await resp.json()
            meals = data.get("meals")
            return meals[0] if meals else None


async def get_categories() -> list[str]:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/categories.php") as resp:
            data = await resp.json()
            return [c["strCategory"] for c in data.get("categories", [])]


async def get_meals_by_category(category: str) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{BASE_URL}/filter.php", params={"c": category}
        ) as resp:
            data = await resp.json()
            return data.get("meals") or []


def parse_ingredients(meal: dict) -> list[str]:
    ingredients = []
    for i in range(1, 21):
        name = meal.get(f"strIngredient{i}", "")
        measure = meal.get(f"strMeasure{i}", "")
        if name and name.strip():
            line = f"{measure.strip()} {name.strip()}".strip()
            ingredients.append(line)
    return ingredients


CAPTION_LIMIT = 1024


def format_meal(meal: dict, for_caption: bool = False) -> str:
    name = meal.get("strMeal", "Без названия")
    category = meal.get("strCategory", "")
    area = meal.get("strArea", "")
    instructions = meal.get("strInstructions", "")
    ingredients = parse_ingredients(meal)

    parts = [f"🍽 <b>{name}</b>"]
    if category:
        parts.append(f"Категория: {category}")
    if area:
        parts.append(f"Кухня: {area}")
    parts.append("")
    parts.append("<b>Ингредиенты:</b>")
    for ing in ingredients:
        parts.append(f"  • {ing}")

    if for_caption:
        text = "\n".join(parts)
        if len(text) > CAPTION_LIMIT:
            text = text[: CAPTION_LIMIT - 3] + "..."
        return text

    parts.append("")
    parts.append("<b>Приготовление:</b>")
    parts.append(instructions)

    youtube = meal.get("strYoutube", "")
    if youtube and youtube.strip():
        parts.append("")
        parts.append(f"🎬 <b>Видео:</b> {youtube}")

    return "\n".join(parts)
