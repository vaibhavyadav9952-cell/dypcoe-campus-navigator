"""
services/ai_service.py - LLM integration for DYPCOE Campus Navigator chatbot.
Supports OpenAI gpt-4o-mini, Google Gemini 1.5 Flash, and keyword fallback.
"""

import re
from typing import List

from app.core.config import settings


async def get_ai_response(
    query: str,
    history: list,
    system_prompt: str,
    locations: list,
) -> str:
    """
    Try OpenAI first, then Gemini, then keyword fallback.
    """
    # --- OpenAI ---
    if settings.OPENAI_API_KEY:
        try:
            return await _openai_response(query, history, system_prompt)
        except Exception as e:
            print(f"[AI] OpenAI error: {e}")

    # --- Gemini ---
    if settings.GEMINI_API_KEY:
        try:
            return await _gemini_response(query, history, system_prompt)
        except Exception as e:
            print(f"[AI] Gemini error: {e}")

    # --- Keyword fallback ---
    return _keyword_fallback(query, locations)


async def _openai_response(query: str, history: list, system_prompt: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-6:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": query})

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=400,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


async def _gemini_response(query: str, history: list, system_prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        system_instruction=system_prompt,
    )

    # Build conversation
    chat_history = []
    for msg in history[-6:]:
        role = "user" if msg.role == "user" else "model"
        chat_history.append({"role": role, "parts": [msg.content]})

    chat = model.start_chat(history=chat_history)
    response = await chat.send_message_async(query)
    return response.text.strip()


def _keyword_fallback(query: str, locations: list) -> str:
    """Simple keyword matching when no AI key is configured."""
    query_lower = query.lower()

    # Match locations by name
    matched = []
    for loc in locations:
        if loc.name.lower() in query_lower or any(
            word in query_lower for word in loc.name.lower().split() if len(word) > 3
        ):
            matched.append(loc)

    if matched:
        loc = matched[0]
        parts = [f"**{loc.name}**"]
        if loc.building:
            parts.append(f"Building: {loc.building}")
        if loc.floor is not None:
            floor_label = "Ground Floor" if loc.floor == 0 else f"Floor {loc.floor}"
            parts.append(f"Floor: {floor_label}")
        if loc.category:
            parts.append(f"Category: {loc.category}")
        if loc.room_number:
            parts.append(f"Room: {loc.room_number}")
        if loc.description:
            parts.append(f"\n{loc.description}")
        parts.append(
            "\nTo get directions, use the **Search** bar in the app — "
            "select your starting point and this location, then click **Get Directions**."
        )
        return "\n".join(parts)

    # Generic response
    return (
        "I couldn't find that specific location in my records. "
        "Please try searching by building name or room number in the search bar, "
        "or visit the Main Reception for assistance. "
        f"I currently have information about {len(locations)} campus locations."
    )
