import aiohttp
import json
import asyncio
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from database import get_ai_setting, save_ai_chat_history, get_ai_chat_history

# Список моделей для переключения
MODELS = [
    "openai/gpt-oss-120b:free",
    "deepseek/deepseek-v4-flash",
    "google/gemini-2.0-flash-lite-preview-02-05:free",
    "qwen/qwen-2.5-7b-instruct:free",
]

async def get_ai_response(user_id: int, user_message: str) -> str:
    print(f"[AI] Запрос от {user_id}: {user_message[:50]}...")
    
    if not OPENROUTER_API_KEY:
        return "❌ ИИ-помощник временно недоступен. Обратитесь к @ZOJlOTOY или @SBveg"
    
    ai_enabled = await get_ai_setting("ai_enabled")
    if ai_enabled != "true":
        return "❌ ИИ-помощник отключен администратором."
    
    # Получаем текущую модель из БД или берем первую
    db_model = await get_ai_setting("ai_model")
    current_model = db_model if db_model else MODELS[0]
    
    # Находим индекс текущей модели
    try:
        model_index = MODELS.index(current_model)
    except ValueError:
        model_index = 0
    
    system_prompt = await get_ai_setting("system_prompt")
    history = await get_ai_chat_history(user_id, 5)
    
    for attempt in range(len(MODELS)):
        model = MODELS[(model_index + attempt) % len(MODELS)]
        print(f"[AI] Попытка {attempt + 1}: {model}")
        
        messages = [{"role": "system", "content": system_prompt}]
        for msg in reversed(history):
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        
        await save_ai_chat_history(user_id, "user", user_message)
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                }
                
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 500
                }
                
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        ai_response = data["choices"][0]["message"]["content"]
                        await save_ai_chat_history(user_id, "assistant", ai_response)
                        
                        # Сохраняем рабочую модель в БД
                        if model != await get_ai_setting("ai_model"):
                            from database import update_ai_setting
                            await update_ai_setting("ai_model", model)
                        
                        print(f"[AI] Успешно! Модель: {model}")
                        return ai_response
                    elif response.status == 429:
                        print(f"[AI] Модель {model} перегружена, пробуем следующую...")
                        continue
                    else:
                        error_text = await response.text()
                        print(f"[AI] Ошибка {response.status} на {model}: {error_text}")
                        continue
                        
        except Exception as e:
            print(f"[AI] Исключение на {model}: {e}")
            continue
    
    return "❌ Все модели временно недоступны. Попробуйте позже."

async def clear_ai_context(user_id: int):
    from database import clear_ai_chat_history
    await clear_ai_chat_history(user_id)
