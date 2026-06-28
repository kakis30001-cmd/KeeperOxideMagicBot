import aiohttp
import json
import asyncio
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from database import get_ai_setting, save_ai_chat_history, get_ai_chat_history

async def get_ai_response(user_id: int, user_message: str) -> str:
    print(f"[AI] Запрос от {user_id}: {user_message[:50]}...")
    
    if not OPENROUTER_API_KEY:
        print("[AI] Нет API ключа!")
        return "❌ ИИ-помощник временно недоступен. Обратитесь к @ZOJlOTOY @SBveg"
    
    ai_enabled = await get_ai_setting("ai_enabled")
    print(f"[AI] ai_enabled: {ai_enabled}")
    
    if ai_enabled != "true":
        return "❌ ИИ-помощник отключен администратором."
    
    # Берем модель из переменной окружения, если в БД нет или она старая
    db_model = await get_ai_setting("ai_model")
    model = db_model or OPENROUTER_MODEL
    
    # Если в БД старая модель - обновляем её
    if db_model and db_model == "mistralai/mistral-7b-instruct:free":
        model = "openai/gpt-oss-120b:free"
        await update_ai_setting("ai_model", model)
        print(f"[AI] Модель в БД обновлена на {model}")
    
    print(f"[AI] Используется модель: {model}")
    
    system_prompt = await get_ai_setting("system_prompt")
    
    history = await get_ai_chat_history(user_id, 5)
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
                "HTTP-Referer": "https://t.me/keepershop",
                "X-Title": "SWEG SHOP AI"
            }
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            print(f"[AI] Отправка запроса в OpenRouter...")
            
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            ) as response:
                print(f"[AI] Статус ответа: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    ai_response = data["choices"][0]["message"]["content"]
                    await save_ai_chat_history(user_id, "assistant", ai_response)
                    print(f"[AI] Ответ получен: {ai_response[:50]}...")
                    return ai_response
                else:
                    error_text = await response.text()
                    print(f"[AI] Ошибка {response.status}: {error_text}")
                    return f"❌ Ошибка {response.status}. Попробуйте позже."
                    
    except asyncio.TimeoutError:
        print("[AI] Таймаут запроса")
        return "⏳ ИИ долго отвечает. Попробуйте еще раз."
    except Exception as e:
        print(f"[AI] Исключение: {e}")
        return "❌ Сервис ИИ временно недоступен."

async def clear_ai_context(user_id: int):
    from database import clear_ai_chat_history
    await clear_ai_chat_history(user_id)
