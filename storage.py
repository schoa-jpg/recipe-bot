import json
import os
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def _favorites_path(user_id: int) -> Path:
    return DATA_DIR / f"{user_id}_favorites.json"


def _ratings_path(user_id: int) -> Path:
    return DATA_DIR / f"{user_id}_ratings.json"


def _load(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_favorite(user_id: int, meal_id: str, meal_name: str):
    path = _favorites_path(user_id)
    data = _load(path)
    data[meal_id] = meal_name
    _save(path, data)


def remove_favorite(user_id: int, meal_id: str):
    path = _favorites_path(user_id)
    data = _load(path)
    data.pop(meal_id, None)
    _save(path, data)


def is_favorite(user_id: int, meal_id: str) -> bool:
    data = _load(_favorites_path(user_id))
    return meal_id in data


def get_favorites(user_id: int) -> dict:
    return _load(_favorites_path(user_id))


def get_favorites_sorted(user_id: int) -> list[tuple[str, str, int]]:
    favs = _load(_favorites_path(user_id))
    ratings = _load(_ratings_path(user_id))
    items = [(mid, name, ratings.get(mid, 0)) for mid, name in favs.items()]
    items.sort(key=lambda x: x[2], reverse=True)
    return items


def set_rating(user_id: int, meal_id: str, rating: int):
    path = _ratings_path(user_id)
    data = _load(path)
    data[meal_id] = rating
    _save(path, data)


def get_rating(user_id: int, meal_id: str) -> int | None:
    data = _load(_ratings_path(user_id))
    return data.get(meal_id)
