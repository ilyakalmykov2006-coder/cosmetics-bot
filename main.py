import os
import asyncio
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.fsm.storage.memory import MemoryStorage
from handlers import register_handlers

# --- Переменные окружения Render ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://cosmetics-bot-xxxx.onrender.com

# --- Инициализация бота ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Регистрируем все обработчики
register_handlers(dp)

# --- FastAPI приложение ---
app = FastAPI()

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    update = types.Update(**await request.json())
    await dp.process_update(update)
    return {"ok": True}

# --- Установка webhook на Render ---
async def on_startup():
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(on_startup())
