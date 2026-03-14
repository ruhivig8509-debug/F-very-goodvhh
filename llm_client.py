"""
llm_client.py - Hugging Face Router API integration via OpenAI SDK.
Handles context building, token truncation, and API calls.
"""

import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client Singleton
# ---------------------------------------------------------------------------

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            raise RuntimeError("HF_TOKEN environment variable is not set")
        _client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=hf_token,
        )
    return _client


MODEL = "moonshotai/Kimi-K2-Instruct-0905:groq"

# Rough char budget – Kimi-K2 supports large contexts but we keep it safe
# to avoid hitting router limits.  ~120k chars ≈ ~30k tokens.
MAX_CONTEXT_CHARS = 100_000


def _truncate_messages(messages: list[dict]) -> list[dict]:
    """FIFO truncation: keep the system prompt (index 0) and trim
    the oldest conversation messages until total chars <= budget."""
    if not messages:
        return messages

    system = messages[0] if messages[0]["role"] == "system" else None
    convo = messages[1:] if system else messages[:]

    total = len(system["content"]) if system else 0
    for m in convo:
        total += len(m.get("content", ""))

    while total > MAX_CONTEXT_CHARS and len(convo) > 1:
        removed = convo.pop(0)
        total -= len(removed.get("content", ""))

    return ([system] + convo) if system else convo


def generate_response(
    system_prompt: str,
    chat_history: list[dict],
    user_message: str,
) -> str:
    """Build the messages array, truncate, and call the LLM."""
    messages = [{"role": "system", "content": system_prompt}]

    for msg in chat_history:
        role = msg.get("role", "user")
        content = msg.get("message_text", "")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message})

    messages = _truncate_messages(messages)

    try:
        client = get_client()
        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.85,
            top_p=0.92,
        )
        return completion.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("LLM API error: %s", exc, exc_info=True)
        return (
            "Arrey yaar 😩, mera dimag hang ho gaya... "
            "Thodi der baad try karo na plz 🥺🌸"
        )


def generate_summary(system_prompt: str, chat_history: list[dict]) -> str:
    """Ask the LLM to summarize the chat history."""
    messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history:
        role = msg.get("role", "user")
        content = msg.get("message_text", "")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": content})

    messages.append(
        {
            "role": "user",
            "content": (
                "Ruhi Ji, pls ek chhota sa summary de do iss poori chat ka — "
                "important points aur vibe dono cover karo, Hinglish mein. 💅✨"
            ),
        }
    )
    messages = _truncate_messages(messages)

    try:
        client = get_client()
        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=600,
            temperature=0.7,
        )
        return completion.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("LLM summary error: %s", exc, exc_info=True)
        return "Summary nahi bana payi 😩... baad mein try karo 🥺"
