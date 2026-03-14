"""
AI Client module for Ruhi Ji Bot
Handles Hugging Face API integration via OpenAI SDK
"""

import logging
from typing import List, Dict, Optional

from openai import OpenAI

from config import (
    HF_TOKEN, LLM_MODEL, LLM_BASE_URL,
    SYSTEM_PROMPT_OWNER, SYSTEM_PROMPT_USER,
    OWNER_USERNAME
)

logger = logging.getLogger(__name__)


class AIClient:
    """Hugging Face LLM client using OpenAI SDK"""
    
    def __init__(self):
        self.client = OpenAI(
            base_url=LLM_BASE_URL,
            api_key=HF_TOKEN,
        )
        self.model = LLM_MODEL
        self._max_context_messages = 30  # Safety limit for context
        self._max_tokens = 500  # Max response tokens
    
    def _truncate_context(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Truncate context to prevent token limit errors (FIFO)"""
        if len(messages) > self._max_context_messages:
            # Keep system prompt + most recent messages
            return messages[:1] + messages[-(self._max_context_messages - 1):]
        return messages
    
    def _get_system_prompt(self, username: str = None, is_owner: bool = False) -> str:
        """Get appropriate system prompt based on user"""
        if is_owner:
            return SYSTEM_PROMPT_OWNER
        return SYSTEM_PROMPT_USER
    
    async def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        username: str = None,
        first_name: str = None,
        is_owner: bool = False
    ) -> str:
        """Generate AI response using Hugging Face API"""
        try:
            # Build system prompt
            system_prompt = self._get_system_prompt(username, is_owner)
            
            # Add user context to system prompt
            if first_name or username:
                name = first_name or username or "User"
                system_prompt += f"\n\nCurrent user's name: {name}"
                if username:
                    system_prompt += f" (@{username})"
            
            # Build messages array
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history
            messages.extend(conversation_history)
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Truncate to prevent token overflow
            messages = self._truncate_context(messages)
            
            logger.info(f"Sending request to LLM with {len(messages)} messages")
            
            # Make API call
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self._max_tokens,
                temperature=0.9,
                top_p=0.95,
            )
            
            response = completion.choices[0].message.content
            logger.info(f"Received response: {response[:100]}...")
            
            return response
            
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            # Return a fallback response in character
            if is_owner:
                return "Owner-sama, kuch technical issue ho gaya 🥺 Please thoda wait karo na... 💕"
            else:
                return "Arre beta, abhi mere mood mein thoda technical glitch aa gaya 😏 Baad mein try karo na 💅"
    
    async def generate_summary(self, messages_text: str) -> str:
        """Generate a summary of recent conversation"""
        try:
            prompt = f"""Summarize this recent conversation in a fun, Gen-Z Hinglish style (2-3 lines max):

{messages_text}

Summary:"""
            
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes conversations in fun Hinglish."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7,
            )
            
            return completion.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            return "Summary generate nahi ho paya bestie 🥺 Technical issue hai"


# Global AI client instance
ai_client = AIClient()
