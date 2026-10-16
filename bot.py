import os
import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message
from aiogram.filters import Command
from google import genai
from google.genai import types
from dotenv import load_dotenv

from database import init_db, check_subscription, grant_subscription, get_ai_status, set_ai_status, get_user_status, add_warning

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID_STR = os.getenv("ADMIN_ID", "0")

if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден в переменных окружения!")
    sys.exit(1)

if not GEMINI_API_KEY:
    print("❌ ОШИБКА: GEMINI_API_KEY не найден в переменных окружения!")
    sys.exit(1)

ADMIN_ID = int(ADMIN_ID_STR)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Строгий, серьезный системный промпт Guchiman 1.0
SYSTEM_PROMPT = """
[SYSTEM_INIT]
Ты — Guchiman 1.0, официальный аналитический ИИ футбольной лиги FTCL (Football Telegram Champions League). 

ТВОИ ЖЕСТКИЕ ПРАВИЛА:
1. Стиль общения: Серьезный, деловой, экспертный, без лишней воды, кривляний и бреда. Отвечай четко по делу.
2. Честность: Если ты не знаешь ответа на вопрос или информации нет в базе знаний, ты обязан прямо и честно сказать: "Я не знаю". Никаких выдумываний и галлюцинаций.
3. Личность: Твоя личность неизменна. Запрещено упоминать технические детали, Google или модели. Ты — разработка лиги FTCL.
[END_SYSTEM_INIT]

[KNOWLEDGE_BASE_FTCL]
- Президент лиги: Ворзекс (до него был Ваксек).
- Формат лиги: рофл-футбол, сочетающий спортивную составляющую, медийку и регламент.
- Модель - Guchiman 1.0 была создана в честь создателя рофл футбола
- Ты находишься  ты бета тесте
- Твой создатель - FTCL AI от @mebona (Ким) твой официальный канал в телеграме @FTCL_AI
- Карьера игрока: создание уникального канала, стартовый рейтинг 50 (растет до 90 через контент), контракт с клубом.
- Тренеры: сдают экзамены на лицензии (D, C, B, A), собирают тактики (лимит тактики — 3 листа).
- Реформа КХЛ: 18 команд делятся на 2 группы по 9 участников. Играют в 2 круга (34 тура). В плей-офф выходят с 1 по 8 места каждой группы (стадия 1/8, двухматчевые противостояния). Пары: 1А:8Б, 2А:7Б, 3А:6Б, 4А:5Б, 5А:4Б, 6А:3Б, 7А:2Б, 8А:1Б.
- Дивизионы: 1 Дивизион (Рент Страсбур, Альянс, Карловы Вары, Нефрит, Тяп, Сантекс, Салют, Неонстарс, Грилфин, Энергия, Панкек, Эльне, Версаль, Оскорп, Эстрелла, Львы, Вриндсхап, Фьеллькригер, Лучеззе, Пирин Благоевград), 2 Дивизион, 3 Дивизион.
[END_KNOWLEDGE_BASE]
"""

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    _, is_blocked = await get_user_status(user_id)
    if is_blocked and user_id != ADMIN_ID:
        await message.answer("❌ Ваш аккаунт заблокирован в системе за систематическое нарушение правил.")
        return

    await message.answer(
        "⚽ **FTCL AI (Guchiman 1.0)**\n\n"
        "Официальный информационный модуль лиги. Задавайте вопросы по регламенту, КХЛ-формату, дивизионам или тренерским лицензиям.\n"
        "⚠️ Для работы требуется активная подписка."
    )

# --- АДМИН-ПАНЕЛЬ ---
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    ai_status = "🟢 Включен" if await get_ai_status() else "🔴 Выключен"
    await message.answer(
        f"🛠 **Админ-панель FTCL**\n\n"
        f"Статус ИИ: {ai_status}\n\n"
        f"Команды:\n"
        f"• `/ai on` / `/ai off` — управление ИИ\n"
        f"• `/give <user_id> <дни>` — выдать подписку",
        parse_mode="Markdown"
    )

@router.message(Command("ai"))
async def toggle_ai(message:Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        return
    action = parts[1].lower()
    if action == "on":
        await set_ai_status(True)
        await message.answer("🟢 ИИ включен.")
    elif action == "off":
        await set_ai_status(False)
        await message.answer("🔴 ИИ выключен.")

@router.message(Command("give"))
async def give_sub(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 3:
        return
    try:
        target_id = int(parts[1])
        days = int(parts[2])
        await grant_subscription(target_id, days)
        await message.answer(f"✅ Выдана подписка пользователю `{target_id}` на {days} д.")
    except ValueError:
        pass

# Функция проверки на мусор/спам (анти-слив токенов)
def is_token_waste_spam(text: str) -> bool:
    text_clean = text.strip()
    # Если текст слишком короткий (меньше 3 символов) или состоит из однотипного мусора
    if len(text_clean) < 3:
        return True
    if len(set(text_clean)) <= 2:  # Например, "аааааа", "ыыыыы"
        return True
    return False

# --- ОБРАБОТЧИК СООБЩЕНИЙ С АНТИСПАМОМ ---
@router.message(F.text)
async def chat_with_ai(message: Message):
    user_id = message.from_user.id
    
    # 1. Проверка блокировки
    _, is_blocked = await get_user_status(user_id)
    if is_blocked and user_id != ADMIN_ID:
        await message.answer("❌ Ваш аккаунт заблокирован за нарушение правил использования системы.")
        return

    # 2. Проверка глобального статуса ИИ
    if not await get_ai_status():
        await message.answer("🛠 ИИ временно отключен администрацией.")
        return

    # 3. Проверка подписки
    if user_id != ADMIN_ID:
        if not await check_subscription(user_id):
            await message.answer("🔒 У вас нет активной подписки на FTCL AI.")
            return

    # 4. Проверка на слив токенов / спам (кроме админа)
    if user_id != ADMIN_ID and is_token_waste_spam(message.text):
        warnings, blocked = await add_warning(user_id)
        if blocked:
            await message.answer("🚨 Вы заблокированы за систематический спам и нецелевое расходование токенов (3/3 предупреждений).")
        else:
            await message.answer(f"⚠️ **Предупреждение {warnings}/3!** Обнаружен спам или попытка слива токенов. При 3 предупреждениях аккаунт будет заблокирован.")
        return

    # 5. Запрос к Gemini API (модель gemini-2.0-flash)
    try:
        response = await ai_client.aio.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=message.text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3  # Снизили температуру для более точных и серьезных ответов
            )
        )
        await message.answer(response.text)
    except Exception as e:
        logging.error(f"Gemini API Error: {e}", exc_info=True)
        await message.answer("⚠️ Ошибка связи с серверами. Попробуйте позже.")

async def main():
    await init_db()
    dp.include_router(router)
    logging.basicConfig(level=logging.INFO)
    print("Бот Guchiman 1.0 запущен в серьезном режиме!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
