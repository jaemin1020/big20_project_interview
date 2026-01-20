from sqlmodel import SQLModel, create_engine, Session, Field, JSON, Column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, Dict, Any
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:1234@postgres:5432/interview_db")
engine = create_engine(DATABASE_URL)

class InterviewSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None)
    user_name: str
    position: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="started")
    emotion_summary: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSONB)
    )

class InterviewRecord(SQLModel, table=True):
    """질문과 답변을 하나의 테이블에서 관리 (ai-worker 버전)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(index=True)
    question_text: str
    order: int
    answer_text: Optional[str] = None
    evaluation: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSONB)
    )
    emotion_summary: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSONB)
    )
    answered_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

def update_record_evaluation(record_id: int, evaluation: dict):
    with Session(engine) as session:
        record = session.get(InterviewRecord, record_id)
        if record:
            record.evaluation = evaluation
            session.add(record)
            session.commit()

def update_record_emotion(record_id: int, emotion: dict):
    with Session(engine) as session:
        record = session.get(InterviewRecord, record_id)
        if record:
            record.emotion_summary = emotion
            session.add(record)
            session.commit()

def update_session_emotion(session_id: int, emotion: dict):
    with Session(engine) as session:
        interview_session = session.get(InterviewSession, session_id)
        if interview_session:
            interview_session.emotion_summary = emotion
            session.add(interview_session)
            session.commit()
