import os
import asyncio
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.fsm.storage.memory import MemoryStorage
from handlers import register_handlers
import uvicorn

# --- Переменные окружения ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://yourproject.up.railway.app
PORT = int(os.environ.get("PORT", 8000))  # Railway задаёт порт автоматически

# --- Инициализация бота и диспетчера ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
register_handlers(dp)

# --- FastAPI приложение ---
app = FastAPI()


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Получает апдейты от Telegram"""
    update = types.Update(**await request.json())
    await dp.process_update(update)
    return {"ok": True}


async def on_startup():
    """Настройка вебхука при запуске"""
    webhook_full_url = WEBHOOK_URL + WEBHOOK_PATH
    print(f"🔗 Устанавливаем webhook: {webhook_full_url}")
    await bot.delete_webhook()
    await bot.set_webhook(webhook_full_url)


@app.on_event("startup")
async def startup_event():
    await on_startup()
    print("✅ Бот успешно запущен и webhook установлен.")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)
