"""
main.py - FastAPI application entrypoint for DYPCOE Smart Campus Navigator.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database import engine, Base
import app.models  # noqa: register all models
from app.api import auth, locations, navigation, admin, chatbot, v1

# Create all tables on startup
Base.metadata.create_all(bind=engine)

# Seed default admin user if none exists
def _seed_default_admin():
    from app.database import SessionLocal
    from app.models import User
    from app.security import get_password_hash
    db = SessionLocal()
    try:
        if db.query(User).filter(User.is_admin == True).count() == 0:
            admin_user = User(
                email="admin@dypcoe.ac.in",
                hashed_password=get_password_hash("dypcoe@2024"),
                is_admin=True,
            )
            db.add(admin_user)
            db.commit()
            print("[startup] Default admin created: admin@dypcoe.ac.in / dypcoe@2024")
    finally:
        db.close()

_seed_default_admin()

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="DYPCOE Smart Campus Navigator API",
    description=(
        "Backend API for DYPCOE Smart Campus Navigator — "
        "Dr. D.Y. Patil College of Engineering, Akurdi, Pune"
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(locations.router)
app.include_router(navigation.router)
app.include_router(admin.router)
app.include_router(chatbot.router)
app.include_router(v1.router)


@app.get("/", tags=["root"])
def root():
    return {
        "message": "DYPCOE Smart Campus Navigator API",
        "campus": "Dr. D.Y. Patil College of Engineering, Akurdi, Pune",
        "version": "1.0.0",
        "docs": "/api/docs",
    }


@app.get("/health", tags=["root"])
def health():
    return {"status": "ok", "campus": "DYPCOE Akurdi"}
