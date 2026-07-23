import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

from dotenv import load_dotenv
from telegram import Update, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

import api
import ai
import storage
from keyboards import (
    recipe_buttons,
    favorites_list_buttons,
    category_buttons,
    meal_select_buttons,
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

WAITING_PHOTO = 1

WELCOME = (
    "👋 Привет! Я бот для поиска рецептов.\n\n"
    "📖 Поиск рецептов:\n"
    "/search <название> — поиск рецепта\n"
    "/ingredient <ингредиент> — поиск по ингредиенту\n"
    "/random — случайный рецепт\n"
    "/categories — категории блюд\n"
    "/favorites — мои избранные рецепты\n\n"
    "🤖 ИИ-помощник:\n"
    "/ai <вопрос> — спроси о кулинарии\n"
    "/fridge <ингредиенты> — рецепт из того, что есть\n"
    "/photo — отправь фото еды, я определю блюдо\n"
    "/chat2 <вопрос> — чат с DeepSeek (быстрый и дешёвый)"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    log.info(f"search query: '{query}', args: {context.args}")
    if not query:
        await update.message.reply_text("Введите название: /search паста")
        return

    await update.message.reply_text("🔍 Ищу...")
    try:
        meals = await api.search_meals(query)
    except Exception as e:
        log.error(f"search_meals error: {e}")
        await update.message.reply_text(f"Ошибка поиска: {e}")
        return
    log.info(f"search_meals returned {len(meals)} results")
    if not meals:
        await update.message.reply_text("Ничего не найдено 😕")
        return

    if len(meals) == 1:
        await _send_meal(update, meals[0])
    else:
        await update.message.reply_text(
            f"Найдено {len(meals)} рецептов. Выберите:",
            reply_markup=meal_select_buttons(meals),
        )


async def cmd_ingredient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Введите ингредиент: /ingredient курица")
        return

    await update.message.reply_text("🔍 Ищу...")
    meals = await api.search_by_ingredient(query)
    if not meals:
        await update.message.reply_text("Ничего не найдено 😕")
        return

    if len(meals) == 1:
        full = await api.get_meal_by_id(meals[0]["idMeal"])
        if full:
            await _send_meal(update, full)
    else:
        await update.message.reply_text(
            f"Найдено {len(meals)} рецептов. Выберите:",
            reply_markup=meal_select_buttons(meals),
        )


async def cmd_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎲 Генерирую...")
    meal = await api.get_random_meal()
    if meal:
        await _send_meal(update, meal)
    else:
        await update.message.reply_text("Не удалось получить рецепт 😕")


async def cmd_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = await api.get_categories()
    translated_cats = [api._tr(c, "en->ru") for c in cats]
    cat_map = dict(zip(translated_cats, cats))
    context.user_data["cat_map"] = cat_map
    buttons = []
    items = list(cat_map.items())
    for i in range(0, len(items), 2):
        row = [
            InlineKeyboardButton(items[i][0], callback_data=f"cat:{items[i][1]}")
        ]
        if i + 1 < len(items):
            row.append(
                InlineKeyboardButton(items[i + 1][0], callback_data=f"cat:{items[i + 1][1]}")
            )
        buttons.append(row)
    await update.message.reply_text(
        "📂 Выберите категорию:", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cmd_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    favs = storage.get_favorites(user_id)
    if not favs:
        await update.message.reply_text("У вас пока нет избранных рецептов.")
        return
    await update.message.reply_text(
        "❤️ Ваши избранные (по рейтингу):", reply_markup=favorites_list_buttons(user_id)
    )


async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text(
            "Спроси что-нибудь о кулинарии!\n"
            "/ai как приготовить идеальный стейк\n"
            "/ai диетические рецепты на ужин\n"
            "/ai что приготовить из курицы"
        )
        return
    await update.message.reply_text("🤖 Думаю...")
    answer = await ai.ask_ai(query)
    for chunk in api._chunk_text(answer, 4000):
        await update.message.reply_text(chunk)


async def cmd_fridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ingredients = " ".join(context.args) if context.args else ""
    if not ingredients:
        await update.message.reply_text(
            "Напиши что есть в холодильнике!\n"
            "/fridge курица, рис, перец, лук\n"
            "/fridge яйца, мука, молоко"
        )
        return
    await update.message.reply_text("🍳 Придумываю рецепт...")
    prompt = (
        f"Придумай рецепт из следующих ингредиентов: {ingredients}.\n"
        f"Дай название, список ингредиентов с точными мерами и пошаговое приготовление."
    )
    answer = await ai.ask_ai(prompt)
    for chunk in api._chunk_text(answer, 4000):
        await update.message.reply_text(chunk)


async def cmd_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 Отправь мне фото еды, и я определю блюdo и дам рецепт!"
    )
    return WAITING_PHOTO


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_url = file.url
    await update.message.reply_text("🔍 Анализирую фото...")
    answer = await ai.analyze_image(image_url)
    for chunk in api._chunk_text(answer, 4000):
        await update.message.reply_text(chunk)
    return ConversationHandler.END


async def cancel_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return
    await update.message.reply_text("🤖 Думаю...")
    answer = await ai.ask_ai(text)
    for chunk in api._chunk_text(answer, 4000):
        await update.message.reply_text(chunk)


async def cmd_chat2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Напиши вопрос: /chat2 привет")
        return
    await update.message.reply_text("💬 DeepSeek думает...")
    answer = await ai.ask_ai(query, model="deepseek/deepseek-chat")
    for chunk in api._chunk_text(answer, 4000):
        await update.message.reply_text(chunk)


async def _send_meal(update_or_query, meal: dict):
    user_id = None
    if isinstance(update_or_query, Update):
        user_id = update_or_query.effective_user.id
    else:
        user_id = update_or_query.from_user.id

    try:
        translated = api.translate_meal_sync(meal)
        log.info(f"_send_meal translated: {translated.get('strMeal', '???')}")
    except Exception as e:
        log.error(f"translate_meal error: {e}")
        translated = meal

    thumb = translated.get("strMealThumb")
    meal_id = meal["idMeal"]
    kb = recipe_buttons(meal_id, user_id)

    if thumb:
        try:
            caption = api.format_meal(translated, for_caption=True)
            await update_or_query.message.reply_photo(
                photo=thumb, caption=caption, parse_mode="HTML", reply_markup=kb
            )
            full_text = api.format_meal(translated, for_caption=False)
            if len(caption) < len(full_text):
                await update_or_query.message.reply_text(
                    full_text, parse_mode="HTML"
                )
            return
        except Exception as e:
            log.error(f"reply_photo error: {e}")

    text = api.format_meal(translated, for_caption=False)
    await update_or_query.message.reply_text(
        text, parse_mode="HTML", reply_markup=kb
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("meal:"):
        meal_id = data.split(":")[1]
        log.info(f"meal callback: meal_id={meal_id}")
        meal = await api.get_meal_by_id(meal_id)
        if meal:
            try:
                translated = api.translate_meal_sync(meal)
                log.info(f"translated name: {translated.get('strMeal', '???')}")
            except Exception as e:
                log.error(f"translate_meal error: {e}")
                translated = meal
            thumb = translated.get("strMealThumb")
            kb = recipe_buttons(meal_id, user_id)
            if thumb:
                try:
                    caption = api.format_meal(translated, for_caption=True)
                    await query.edit_message_media(
                        media=InputMediaPhoto(thumb, caption=caption, parse_mode="HTML"),
                        reply_markup=kb,
                    )
                    full_text = api.format_meal(translated, for_caption=False)
                    if len(caption) < len(full_text):
                        await query.message.reply_text(full_text, parse_mode="HTML")
                    return
                except Exception as e:
                    log.error(f"edit_message_media error: {e}")
            text = api.format_meal(translated, for_caption=False)
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    elif data.startswith("fav_toggle:"):
        meal_id = data.split(":")[1]
        if storage.is_favorite(user_id, meal_id):
            storage.remove_favorite(user_id, meal_id)
            await query.answer("💔 Удалено из избранного")
        else:
            meal = await api.get_meal_by_id(meal_id)
            if meal:
                try:
                    translated = api.translate_meal_sync(meal)
                except Exception:
                    translated = meal
                storage.add_favorite(user_id, meal_id, translated["strMeal"])
            await query.answer("❤️ Добавлено в избранное!")

        meal = await api.get_meal_by_id(meal_id)
        if meal:
            kb = recipe_buttons(meal_id, user_id)
            await query.edit_message_reply_markup(reply_markup=kb)

    elif data.startswith("rate:"):
        parts = data.split(":")
        meal_id = parts[1]
        rating = int(parts[2])
        storage.set_rating(user_id, meal_id, rating)
        await query.answer(f"⭐ Вы поставили {rating} из 5")

        kb = recipe_buttons(meal_id, user_id)
        await query.edit_message_reply_markup(reply_markup=kb)

    elif data.startswith("cat:"):
        category = data.split(":", 1)[1]
        meals = await api.get_meals_by_category(category)
        if meals:
            translated_cat = api._tr(category, "en->ru")
            translated_meals = []
            for m in meals[:10]:
                name = api._tr(m.get("strMeal", "???"), "en->ru")
                translated_meals.append((m["idMeal"], name))
            buttons = []
            for mid, name in translated_meals:
                buttons.append([InlineKeyboardButton(name, callback_data=f"meal:{mid}")])
            await query.edit_message_text(
                f"📂 {translated_cat} — {len(meals)} рецептов. Выберите:",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        else:
            await query.edit_message_text("В этой категории нет рецептов 😕")

    elif data.startswith("fav_view:"):
        meal_id = data.split(":")[1]
        meal = await api.get_meal_by_id(meal_id)
        if meal:
            try:
                translated = api.translate_meal_sync(meal)
            except Exception as e:
                log.error(f"translate error: {e}")
                translated = meal
            thumb = translated.get("strMealThumb")
            kb = recipe_buttons(meal_id, user_id)
            if thumb:
                try:
                    caption = api.format_meal(translated, for_caption=True)
                    await query.edit_message_media(
                        media=InputMediaPhoto(thumb, caption=caption, parse_mode="HTML"),
                        reply_markup=kb,
                    )
                    full_text = api.format_meal(translated, for_caption=False)
                    if len(caption) < len(full_text):
                        await query.message.reply_text(full_text, parse_mode="HTML")
                    return
                except Exception as e:
                    log.error(f"edit_message_media error: {e}")
            text = api.format_meal(translated, for_caption=False)
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    photo_conv = ConversationHandler(
        entry_points=[CommandHandler("photo", cmd_photo)],
        states={
            WAITING_PHOTO: [
                MessageHandler(filters.PHOTO, handle_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_photo)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("ingredient", cmd_ingredient))
    app.add_handler(CommandHandler("random", cmd_random))
    app.add_handler(CommandHandler("categories", cmd_categories))
    app.add_handler(CommandHandler("favorites", cmd_favorites))
    app.add_handler(CommandHandler("ai", cmd_ai))
    app.add_handler(CommandHandler("fridge", cmd_fridge))
    app.add_handler(CommandHandler("chat2", cmd_chat2))
    app.add_handler(photo_conv)
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text))

    PORT = os.getenv("PORT")
    if PORT:
        import asyncio
        import uvicorn
        from fastapi import FastAPI, Request
        from telegram import Update as TgUpdate

        web_app = FastAPI()

        @web_app.on_event("startup")
        async def on_startup():
            await app.initialize()
            await app.start()
            RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
            WEBHOOK_URL = f"{RENDER_URL}/webhook"
            await app.bot.set_webhook(WEBHOOK_URL)
            log.info(f"Webhook set: {WEBHOOK_URL}")

        @web_app.on_event("shutdown")
        async def on_shutdown():
            await app.stop()
            await app.shutdown()

        @web_app.get("/")
        async def health():
            return {"status": "ok"}

        @web_app.post("/webhook")
        async def webhook(request: Request):
            data = await request.json()
            update = TgUpdate.de_json(data, app.bot)
            await app.process_update(update)
            return {"ok": True}

        log.info(f"Starting webhook on port {PORT}")
        uvicorn.run(web_app, host="0.0.0.0", port=int(PORT))
    else:
        log.info("Starting polling mode")
        app.run_polling()


if __name__ == "__main__":
    main()
