from aiogram import types, Dispatcher
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.dispatcher.fsm.context import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from sheets import get_catalog
import os
from main import bot  # безопасный импорт, т.к. bot создаётся до импорта handlers

# FSM состояния для корзины
class Cart(StatesGroup):
    waiting_for_item = State()

def register_handlers(dp: Dispatcher):
    dp.message.register(start, commands=["start"])
    dp.message.register(show_catalog, commands=["catalog"])
    dp.callback_query.register(add_to_cart_callback, lambda c: c.data.startswith("add_"))
    dp.message.register(show_cart, commands=["cart"])
    dp.message.register(send_order, commands=["order"])


# --- Команда /start ---
async def start(message: types.Message):
    await message.answer(
        "👋 Привет! Это каталог косметики.\n\n"
        "🛍 Используй /catalog чтобы посмотреть товары.\n"
        "🧺 Используй /cart чтобы посмотреть корзину.\n"
        "📦 Используй /order чтобы оформить заказ."
    )


# --- Показ каталога ---
async def show_catalog(message: types.Message):
    catalog = get_catalog()
    if not catalog:
        await message.answer("Каталог пуст.")
        return

    for item in catalog:
        name = item.get("name")
        price = item.get("price")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Добавить в корзину", callback_data=f"add_{name}")]
        ])
        await message.answer(f"💄 {name}\n💰 Цена: {price} ₽", reply_markup=kb)


# --- Добавление в корзину ---
async def add_to_cart_callback(callback: types.CallbackQuery, state: FSMContext):
    item_name = callback.data.replace("add_", "")
    data = await state.get_data()
    cart = data.get("cart", [])
    cart.append(item_name)
    await state.update_data(cart=cart)
    await callback.answer(f"{item_name} добавлен в корзину 🛒")


# --- Показ корзины ---
async def show_cart(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    if cart:
        await message.answer(
            "🧺 Ваша корзина:\n" + "\n".join(cart) + "\n\nЧтобы оформить заказ, используйте /order"
        )
    else:
        await message.answer("Корзина пуста.")


# --- Отправка заявки ---
async def send_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    if not cart:
        await message.answer("Корзина пуста.")
        return

    admin_id = int(os.environ.get("ADMIN_ID"))
    order_text = (
        f"📩 Новая заявка от @{message.from_user.username or message.from_user.full_name}:\n\n"
        + "\n".join([f"- {item}" for item in cart])
    )

    await message.answer("✅ Заявка отправлена администратору! Мы свяжемся с вами.")
    await bot.send_message(admin_id, order_text)
    await state.clear()
