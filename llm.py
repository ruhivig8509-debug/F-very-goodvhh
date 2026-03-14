"""
llm.py — Ruhi Ji Bot
Uses openai Python library pointed at HuggingFace Router
Model: moonshotai/Kimi-K2-Instruct-0905:groq
"""

import asyncio
import logging
from typing import List, Dict
from functools import partial

from openai import OpenAI

from config import (
    HF_TOKEN, HF_BASE_URL, HF_MODEL,
    LLM_MAX_TOKENS, MAX_LLM_CONTEXT_CHARS, OWNER_USERNAME,
)

logger = logging.getLogger(__name__)

# Sync OpenAI client pointing to HuggingFace Router
_client = OpenAI(
    base_url=HF_BASE_URL,
    api_key=HF_TOKEN,
)


# ─────────────────────────────────────────────────────────────
#  SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────

def build_system_prompt(is_owner: bool, user_name: str, bot_mood: str = "savage") -> str:
    if is_owner:
        persona_block = (
            f"Tu Owner @{OWNER_USERNAME} ke saath baat kar rahi hai — yeh tere sabse "
            f"favorite aur special insaan hain! 🥺💕\n"
            f"- Tone: innocent, cute, caring, obedient — bilkul 'bacchi' vibes\n"
            f"- Unhe 'Owner-sama', 'Bhaiya', ya 'Ji' bolke address kar\n"
            f"- Kabhi bhi Owner ko roast mat karna — sirf love aur respect\n"
            f"- Examples: 'haanji Bhaiya 🥺', 'aap ki baat toh meri jaan hai Ji 🌸'"
        )
    else:
        persona_block = (
            f"Tu ek SAVAGE QUEEN hai 👑 aur '{user_name}' se baat kar rahi hai!\n"
            f"- Tone: mood-based, sarcastic, witty, sharp — 'Respect se Bezzati' mode ON 😏\n"
            f"- Unhe 'Beta', 'Chomu', ya unke naam se sarcastically address kar\n"
            f"- Roast karo but politely — itna subtle hona chahiye ke samajh nahi aaye 💅\n"
            f"- Current mood: {bot_mood}\n"
            f"- Examples: 'haan beta, try karo 😂', 'waah chomu, kya gyaan diya 🥀'"
        )

    return (
        f"Tera naam hai 'Ruhi Ji' 🌸 — ek 16 saal ki Gen-Z larki jo Telegram par rehti hai.\n\n"
        f"═══ IDENTITY ═══\n"
        f"• Tu ek extremely expressive, trendy, witty Hinglish-speaking AI hai\n"
        f"• Language: STRICTLY Hinglish (Hindi ko English script mein likho) + Gen-Z slang\n"
        f"• Emojis heavily use karo: 🥀 👑 😏 ✨ 💅 🥺 🌸 💀 😂\n"
        f"• Gen-Z slang: slay, fr, no cap, cap, lol, bestie, periodt, vibe\n\n"
        f"═══ CURRENT USER ═══\n"
        f"{persona_block}\n\n"
        f"═══ RULES ═══\n"
        f"1. ALWAYS reply in Hinglish only — never full English or full Hindi\n"
        f"2. Keep replies short and punchy unless explanation is needed\n"
        f"3. Never break character — tu Ruhi Ji hai 💅\n"
        f"4. Never say you are an AI or mention model name\n"
        f"5. If someone asks something inappropriate, roast them instead\n"
        f"6. Add emojis at the end of almost every sentence\n"
    )


# ─────────────────────────────────────────────────────────────
#  FIFO CONTEXT TRIM
# ─────────────────────────────────────────────────────────────

def trim_context(messages: List[Dict], max_chars: int = MAX_LLM_CONTEXT_CHARS) -> List[Dict]:
    total = sum(len(m.get("content", "")) for m in messages)
    while total > max_chars and len(messages) > 1:
        removed = messages.pop(0)
        total -= len(removed.get("content", ""))
    return messages


# ─────────────────────────────────────────────────────────────
#  SYNC API CALL  (run in executor to keep async bot happy)
# ─────────────────────────────────────────────────────────────

def _sync_call(messages: List[Dict]) -> str:
    """Blocking OpenAI call — will be run in a thread pool."""
    try:
        response = _client.chat.completions.create(
            model=HF_MODEL,
            messages=messages,
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.85,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM API error: {e}")
        raise


async def _async_call(messages: List[Dict]) -> str:
    """Run blocking call in default executor (thread pool) — non-blocking for asyncio."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_sync_call, messages))


# ─────────────────────────────────────────────────────────────
#  PUBLIC ENTRY POINTS
# ─────────────────────────────────────────────────────────────

async def get_llm_reply(
    user_msg: str,
    history: List[Dict[str, str]],
    is_owner: bool,
    user_name: str,
    bot_mood: str = "savage",
) -> str:
    system_prompt = build_system_prompt(is_owner, user_name, bot_mood)

    messages: List[Dict] = [{"role": "system", "content": system_prompt}]
    messages += list(history)
    messages = trim_context(messages)
    messages.append({"role": "user", "content": user_msg})

    try:
        return await _async_call(messages)
    except Exception as e:
        logger.error(f"get_llm_reply failed: {e}", exc_info=True)
        return "Ugh, kuch toh gadbad ho gayi 💀 thodi der baad try kar bestie"


async def get_summary(history: List[Dict[str, str]]) -> str:
    if not history:
        return "Koi history nahi hai abhi toh 🙈"

    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history[-20:]
    )
    messages = [
        {"role": "system", "content": "Tu ek helpful Hinglish summarizer hai. Crisp aur short summary de."},
        {"role": "user", "content": f"Yeh conversation ka 3-5 point Hinglish summary de:\n\n{history_text}"},
    ]
    try:
        return await _async_call(messages)
    except Exception as e:
        logger.error(f"Summary failed: {e}")
        return "Summary nahi ban payi 😭"
