from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from storage import is_favorite, get_rating, get_favorites_sorted
import api


def recipe_buttons(meal_id: str, user_id: int) -> InlineKeyboardMarkup:
    fav_text = "💔 Убрать из избранного" if is_favorite(user_id, meal_id) else "❤️ В избранное"

    buttons = [
        [InlineKeyboardButton(fav_text, callback_data=f"fav_toggle:{meal_id}")],
    ]
    buttons.append(rating_row(meal_id, user_id))
    return InlineKeyboardMarkup(buttons)


def rating_row(meal_id: str, user_id: int) -> list[InlineKeyboardButton]:
    current = get_rating(user_id, meal_id)
    row = []
    for i in range(1, 6):
        star = "⭐" if (current and i <= current) else "☆"
        row.append(InlineKeyboardButton(star, callback_data=f"rate:{meal_id}:{i}"))
    return row


def favorites_list_buttons(user_id: int) -> InlineKeyboardMarkup:
    items = get_favorites_sorted(user_id)
    buttons = []
    for meal_id, meal_name, rating in items:
        stars = f" {'⭐' * rating}" if rating else ""
        buttons.append(
            [InlineKeyboardButton(
                f"🍽 {meal_name}{stars}",
                callback_data=f"fav_view:{meal_id}",
            )]
        )
    return InlineKeyboardMarkup(buttons)


def category_buttons(categories: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for i in range(0, len(categories), 2):
        row = [
            InlineKeyboardButton(categories[i], callback_data=f"cat:{categories[i]}")
        ]
        if i + 1 < len(categories):
            row.append(
                InlineKeyboardButton(categories[i + 1], callback_data=f"cat:{categories[i + 1]}")
            )
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def meal_select_buttons(meals: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for meal in meals[:10]:
        name = api._tr(meal.get("strMeal", "???"), "en->ru")
        buttons.append(
            [
                InlineKeyboardButton(
                    name,
                    callback_data=f"meal:{meal['idMeal']}",
                )
            ]
        )
    return InlineKeyboardMarkup(buttons)
