"""
Database layer for EquiSkill.
Defines SQLAlchemy models and session factory.
Tables are auto-created on first run.
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://equiskill:equiskill@localhost:3306/equiskill"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------- ORM Models ----------

class ChatSession(Base):
    """Persists every user message + AI reply across all chat modes."""
    __tablename__ = "chat_sessions"

    id         = Column(Integer, primary_key=True, index=True)
    mode       = Column(String(50), nullable=False, index=True)
    user_msg   = Column(Text, nullable=False)
    ai_reply   = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class GeneratedResume(Base):
    """Stores AI-generated LaTeX resume code."""
    __tablename__ = "generated_resumes"

    id         = Column(Integer, primary_key=True, index=True)
    latex_code = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def create_tables():
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session and ensures it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
