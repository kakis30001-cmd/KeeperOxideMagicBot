import aiohttp
import json
import asyncio
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from database import get_ai_setting, save_ai_chat_history, get_ai_chat_history

_last_request_time = 0
_request_lock = asyncio.Lock()
REQUEST_DELAY = 3

async def get_ai_response(user_id: int, user_message: str) -> str:
    global _last_request_time
    
    if not OPENROUTER_API_KEY:
        return "❌ Джарвис временно недоступен. Напишите продавцам @ZOJlOTOY или @SBveg"
    
    ai_enabled = await get_ai_setting("ai_enabled")
    if ai_enabled != "true":
        return "❌ Джарвис отключен. Обратитесь к @ZOJlOTOY"
    
    async with _request_lock:
        now = asyncio.get_event_loop().time()
        if now - _last_request_time < REQUEST_DELAY:
            await asyncio.sleep(REQUEST_DELAY - (now - _last_request_time))
        _last_request_time = asyncio.get_event_loop().time()
    
    model = OPENROUTER_MODEL or await get_ai_setting("ai_model") or "openai/gpt-oss-120b:free"
    
    system_prompt = await get_ai_setting("system_prompt")
    if not system_prompt:
        system_prompt = """
Ты - Джарвис, ИИ-ассистент магазина SWEG CHEATS.
Отвечаешь ТОЛЬКО на вопросы о чите MAGIC.
Если не знаешь - скажи обратиться к @ZOJlOTOY или @SBveg.
Отвечай кратко (2-3 предложения).
Всегда советуй VIP версию, если спрашивают о сравнении с LIGHT.
"""
    
    history = await get_ai_chat_history(user_id, 3)
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in reversed(history):
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": user_message})
    
    await save_ai_chat_history(user_id, "user", user_message)
    
    print(f"[AI] Модель: {model}")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/keepershop",
                "X-Title": "SWEG CHEATS AI"
            }
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 200
            }
            
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=15
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    ai_response = data["choices"][0]["message"]["content"]
                    await save_ai_chat_history(user_id, "assistant", ai_response)
                    return ai_response
                elif response.status == 429:
                    return "⏳ Джарвис перегружен. Попробуйте через минуту или напишите @ZOJlOTOY"
                elif response.status == 402:
                    return "💳 Лимит ИИ исчерпан. Обратитесь к @ZOJlOTOY"
                else:
                    return f"❌ Ошибка {response.status}. Напишите продавцам @ZOJlOTOY или @SBveg"
                    
    except asyncio.TimeoutError:
        return "⏳ Джарвис долго отвечает. Напишите @ZOJlOTOY или @SBveg"
    except Exception as e:
        print(f"[AI Exception] {e}")
        return "❌ Джарвис временно недоступен. Обратитесь к @ZOJlOTOY или @SBveg"

async def clear_ai_context(user_id: int):
    from database import clear_ai_chat_history
    await clear_ai_chat_history(user_id)
