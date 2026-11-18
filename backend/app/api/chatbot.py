"""
api/chatbot.py - AI chatbot endpoint for DYPCOE Campus Navigator.
Supports OpenAI gpt-4o-mini, Google Gemini, and keyword fallback.
"""

import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Location, ChatHistory
from app.schemas import ChatRequest, ChatResponse, LocationResponse
from app.services.ai_service import get_ai_response

router = APIRouter(prefix="/api", tags=["chatbot"])

DYPCOE_SYSTEM_PROMPT = """You are a friendly and helpful campus navigation assistant for DYPCOE — 
Dr. D.Y. Patil College of Engineering, Akurdi, Pune, Maharashtra, India.

You help students, faculty, and visitors:
- Find buildings, labs, classrooms, offices, and facilities on campus
- Understand which floor and building a room is on
- Get general directions and navigation tips
- Learn about campus facilities

Campus locations available:
{locations_json}

Guidelines:
- When asked about a location, mention its building, floor, and category.
- When asked for turn-by-turn directions, tell the user to use the Search bar in the app to select Start and End locations, then click "Get Directions".
- If a location is not in your list, say you're not sure and suggest asking at the main reception.
- Keep answers concise, friendly, and accurate.
- Do not invent corridors, room numbers, or paths that are not in the data.
- If indoor navigation is needed but unavailable, clearly say so and direct to building entrance.
"""


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    # Fetch all campus locations for context
    locations = db.query(Location).order_by(Location.name).all()
    loc_data = [
        {
            "id": l.id,
            "name": l.name,
            "category": l.category,
            "building": l.building,
            "floor": l.floor,
            "room_number": l.room_number,
            "description": l.description,
            "is_navigable": l.is_navigable,
        }
        for l in locations
    ]
    system_prompt = DYPCOE_SYSTEM_PROMPT.format(
        locations_json=json.dumps(loc_data, indent=2)
    )

    response_text = await get_ai_response(
        query=req.query,
        history=req.conversation_history,
        system_prompt=system_prompt,
        locations=locations,
    )

    # Log to DB (best-effort)
    try:
        log = ChatHistory(
            session_id=req.session_id or "anonymous",
            user_query=req.query,
            ai_response=response_text,
        )
        db.add(log)
        db.commit()
    except Exception:
        pass

    # Try to extract suggested locations (simple keyword match on response)
    suggested = []
    for loc in locations:
        if loc.name.lower() in response_text.lower():
            suggested.append(LocationResponse.model_validate(loc))
            if len(suggested) >= 3:
                break

    return ChatResponse(response=response_text, suggested_locations=suggested)
