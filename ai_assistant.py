import aiohttp
import json
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from database import get_ai_setting, save_ai_chat_history, get_ai_chat_history

async def get_ai_response(user_id: int, user_message: str) -> str:
    if not OPENROUTER_API_KEY:
        return "❌ ИИ-помощник временно недоступен. Обратитесь к @nikita1055"
    
    ai_enabled = await get_ai_setting("ai_enabled")
    if ai_enabled != "true":
        return "❌ ИИ-помощник отключен администратором."
    
    # Берем модель СНАЧАЛА из переменной окружения, потом из БД
    model = OPENROUTER_MODEL  # из config.py (переменная Railway)
    if not model:
        model = await get_ai_setting("ai_model") or "qwen/qwen3-next-80b-a3b-instruct:free"
    
    system_prompt = await get_ai_setting("system_prompt")
    
    history = await get_ai_chat_history(user_id, 5)
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in reversed(history):
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": user_message})
    
    await save_ai_chat_history(user_id, "user", user_message)
    
    print(f"[AI] Используется модель: {model}")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/keepershop",
                "X-Title": "KeeperShop AI"
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
                    return ai_response
                else:
                    error_text = await response.text()
                    print(f"[AI Error] {response.status}: {error_text}")
                    return f"❌ Ошибка ИИ: {response.status}. Попробуйте позже."
                    
    except Exception as e:
        print(f"[AI Exception] {e}")
        return "❌ Сервис ИИ временно недоступен."

async def clear_ai_context(user_id: int):
    from database import clear_ai_chat_history
    await clear_ai_chat_history(user_id)
