import os
import logging
import asyncio
from fastapi import FastAPI, Request, HTTPException
import uvicorn

from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Update
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
load_dotenv()


from sheets import get_all_products, find_product_by_id, add_product

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Telegram numeric id администратора
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")  # обычно "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # публичный URL, например https://app.onrender.com/webhook

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

app = FastAPI()

# Простое хранение корзин в памяти (для production можно заменить на Redis/БД)
user_carts = {}  # user_id -> {product_id: qty}

# --- States for admin adding product ---
class AddProductStates(StatesGroup):
    id = State()
    name = State()
    category = State()
    price = State()
    stock = State()
    description = State()
    photo = State()
    confirm = State()

# --- Handlers ---
@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    txt = "Привет! Это каталог. Выберите действие:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="🛒 Моя корзина", callback_data="cart")],
        [InlineKeyboardButton(text="📩 Оформить заказ", callback_data="checkout")]
    ])
    await message.answer(txt, reply_markup=kb)

@dp.callback_query(lambda c: c.data == "catalog")
async def show_catalog_cb(query: CallbackQuery):
    await query.answer()
    products = [p for p in get_all_products() if p["active"] and p["stock"] > 0]
    if not products:
        await query.message.answer("Сейчас ничего нет в наличии.")
        return
    # Покажем первые 10 товаров (для простоты). Можно добавить пагинацию.
    for p in products[:30]:
        txt = f"<b>{p['name']}</b>\n{p['description']}\nЦена: {p['price']} грн\nВ наличии: {p['stock']}\nID: {p['id']}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Добавить в корзину", callback_data=f"add_{p['id']}")]
        ])
        if p.get("photo_url"):
            try:
                await query.message.answer_photo(p["photo_url"], caption=txt, reply_markup=kb)
            except Exception:
                await query.message.answer(txt, reply_markup=kb)
        else:
            await query.message.answer(txt, reply_markup=kb)

@dp.callback_query(lambda c: c.data and c.data.startswith("add_"))
async def add_to_cart_cb(query: CallbackQuery):
    await query.answer("Добавлено в корзину ✅")
    user_id = query.from_user.id
    pid = query.data.split("_",1)[1]
    cart = user_carts.setdefault(user_id, {})
    cart[pid] = cart.get(pid, 0) + 1
    await query.message.answer("Товар добавлен. Откройте <b>Моя корзина</b> для оформления.")

@dp.callback_query(lambda c: c.data == "cart")
async def show_cart_cb(query: CallbackQuery):
    await query.answer()
    user_id = query.from_user.id
    cart = user_carts.get(user_id, {})
    if not cart:
        await query.message.answer("Ваша корзина пуста.")
        return
    lines = []
    total = 0
    for pid, qty in cart.items():
        p = find_product_by_id(pid)
        if not p:
            continue
        lines.append(f"{p['name']} x{qty} — {p['price']*qty}")
        total += p['price']*qty
    txt = "\n".join(lines) + f"\n\nИтого: {total}\n\nНажмите Оформить заказ"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton(text="Очистить корзину", callback_data="clear_cart")]
    ])
    await query.message.answer(txt, reply_markup=kb)

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart_cb(query: CallbackQuery):
    user_id = query.from_user.id
    user_carts.pop(user_id, None)
    await query.answer("Корзина очищена.")

@dp.callback_query(lambda c: c.data == "checkout")
async def checkout_cb(query: CallbackQuery):
    user_id = query.from_user.id
    cart = user_carts.get(user_id, {})
    if not cart:
        await query.answer("Корзина пуста.")
        return
    # Отправляем админу заявку
    user = query.from_user
    lines = []
    total = 0
    for pid, qty in cart.items():
        p = find_product_by_id(pid)
        if not p:
            continue
        lines.append(f"{p['name']} x{qty} — {p['price']*qty}")
        total += p['price']*qty
    txt = f"Новая заявка от @{user.username or user.first_name} (id {user.id}):\n\n"
    txt += "\n".join(lines)
    txt += f"\n\nИтого: {total}\n\nНик: @{user.username}\nUserID: {user.id}"
    # отправляем админу
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, txt)
        except Exception as e:
            logger.exception("Не удалось отправить админ сообщение: %s", e)
    await query.message.answer("Заявка отправлена! Я напишу вам в личку после подтверждения.")
    # очищаем корзину
    user_carts.pop(user_id, None)

# --- Admin: добавление товара через бот ---
@dp.message(Command(commands=["add_product"]))
async def cmd_add_product(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return
    await message.answer("Введите ID товара (уникальный):")
    await state.set_state(AddProductStates.id)

@dp.message(lambda m: True, state=AddProductStates.id)
async def admin_get_id(message: Message, state: FSMContext):
    await state.update_data(id=message.text.strip())
    await message.answer("Название товара:")
    await state.set_state(AddProductStates.name)

@dp.message(lambda m: True, state=AddProductStates.name)
async def admin_get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Категория:")
    await state.set_state(AddProductStates.category)

@dp.message(lambda m: True, state=AddProductStates.category)
async def admin_get_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text.strip())
    await message.answer("Цена (числом):")
    await state.set_state(AddProductStates.price)

@dp.message(lambda m: True, state=AddProductStates.price)
async def admin_get_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",","."))
    except:
        await message.answer("Неверный формат. Введите цену числом.")
        return
    await state.update_data(price=price)
    await message.answer("Количество в наличии (целое):")
    await state.set_state(AddProductStates.stock)

@dp.message(lambda m: True, state=AddProductStates.stock)
async def admin_get_stock(message: Message, state: FSMContext):
    try:
        stock = int(message.text)
    except:
        await message.answer("Неверный формат. Введите целое число.")
        return
    await state.update_data(stock=stock)
    await message.answer("Краткое описание:")
    await state.set_state(AddProductStates.description)

@dp.message(lambda m: True, state=AddProductStates.description)
async def admin_get_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer("Ссылка на фото (URL) или отправьте 'нет':")
    await state.set_state(AddProductStates.photo)

@dp.message(lambda m: True, state=AddProductStates.photo)
async def admin_get_photo(message: Message, state: FSMContext):
    photo = message.text.strip()
    await state.update_data(photo=photo if photo.lower() != "нет" else "")
    data = await state.get_data()
    preview = (
        f"ID: {data['id']}\nНазвание: {data['name']}\nКатегория: {data['category']}\n"
        f"Цена: {data['price']}\nВ наличии: {data['stock']}\nОписание: {data['description']}\nФото: {data['photo']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить и добавить", callback_data="admin_confirm_add")],
        [InlineKeyboardButton(text="Отменить", callback_data="admin_cancel_add")]
    ])
    await message.answer("Предпросмотр товара:\n\n" + preview, reply_markup=kb)
    await state.set_state(AddProductStates.confirm)

@dp.callback_query(lambda c: c.data == "admin_confirm_add")
async def admin_confirm_add(query: CallbackQuery, state: FSMContext):
    if query.from_user.id != ADMIN_ID:
        await query.answer("Нет доступа")
        return
    data = await state.get_data()
    add_product({
        "id": data["id"],
        "name": data["name"],
        "category": data["category"],
        "price": data["price"],
        "stock": data["stock"],
        "description": data["description"],
        "photo_url": data["photo"],
        "active": "yes"
    })
    await query.message.answer("Товар добавлен в таблицу ✅")
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_cancel_add")
async def admin_cancel_add(query: CallbackQuery, state: FSMContext):
    if query.from_user.id != ADMIN_ID:
        await query.answer("Нет доступа")
        return
    await query.message.answer("Добавление отменено.")
    await state.clear()

# --- FastAPI route for Telegram webhook ---
@app.post(WEBHOOK_PATH)
async def telegram_webhook(req: Request):
    body = await req.json()
    try:
        update = Update(**body)
    except Exception as e:
        logger.exception("Bad update: %s", e)
        raise HTTPException(status_code=400, detail="Bad update")
    # обрабатываем update
    await dp.process_update(update)
    return {"ok": True}

# --- Startup: устанавливаем вебхук у Telegram ---
@app.on_event("startup")
async def on_startup():
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set — убедитесь, что вы хотите использовать webhook.")
        return
    url = WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH
    # установить webhook
    try:
        await bot.set_webhook(url)
        logger.info("Webhook set to %s", url)
    except Exception as e:
        logger.exception("Failed to set webhook: %s", e)

@app.on_event("shutdown")
async def on_shutdown():
    try:
        await bot.delete_webhook()
    except Exception:
        pass
    await bot.session.close()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
