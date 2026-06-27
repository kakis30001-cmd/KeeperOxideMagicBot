import aiohttp
import json
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from database import get_ai_setting, save_ai_chat_history, get_ai_chat_history

async def get_ai_response(user_id: int, user_message: str) -> str:
    """Получение ответа от ИИ через OpenRouter"""
    
    if not OPENROUTER_API_KEY:
        return "❌ ИИ-помощник временно недоступен. Обратитесь к @nikita1055"
    
    # Проверяем включен ли ИИ
    ai_enabled = await get_ai_setting("ai_enabled")
    if ai_enabled != "true":
        return "❌ ИИ-помощник отключен администратором."
    
    # Получаем системный промпт
    system_prompt = await get_ai_setting("system_prompt")
    model = await get_ai_setting("ai_model") or OPENROUTER_MODEL
    
    # Получаем историю чата
    history = await get_ai_chat_history(user_id, 5)
    messages = [{"role": "system", "content": system_prompt}]
    
    # Добавляем историю
    for msg in reversed(history):
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Добавляем текущее сообщение
    messages.append({"role": "user", "content": user_message})
    
    # Сохраняем сообщение пользователя
    await save_ai_chat_history(user_id, "user", user_message)
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/keepershop",
                "X-Title": "KeeperShop AI Assistant"
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
                timeout=20
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    ai_response = data["choices"][0]["message"]["content"]
                    
                    # Сохраняем ответ ИИ
                    await save_ai_chat_history(user_id, "assistant", ai_response)
                    
                    return ai_response
                else:
                    error_text = await response.text()
                    print(f"[AI Error] {response.status}: {error_text}")
                    return "❌ Ошибка при обращении к ИИ. Попробуйте позже."
                    
    except Exception as e:
        print(f"[AI Exception] {e}")
        return "❌ Сервис ИИ временно недоступен."

async def clear_ai_context(user_id: int):
    """Очистка контекста ИИ для пользователя"""
    from database import clear_ai_chat_history
    await clear_ai_chat_history(user_id)
