from sqlmodel import SQLModel, create_engine, Session, Field, JSON
from typing import Optional
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:1234@postgres:5432/interview_db")
engine = create_engine(DATABASE_URL)

class InterviewSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_name: str
    position: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="started")
    emotion_summary: Optional[dict] = Field(default=None, sa_type=JSON)

class InterviewAnswer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: int
    answer_text: str
    evaluation: Optional[dict] = Field(default=None, sa_type=JSON)
    emotion_summary: Optional[dict] = Field(default=None, sa_type=JSON)
    created_at: datetime = Field(default_factory=datetime.utcnow)

def update_answer_evaluation(answer_id: int, evaluation: dict):
    with Session(engine) as session:
        answer = session.get(InterviewAnswer, answer_id)
        if answer:
            answer.evaluation = evaluation
            session.add(answer)
            session.commit()

def update_answer_emotion(answer_id: int, emotion: dict):
    with Session(engine) as session:
        answer = session.get(InterviewAnswer, answer_id)
        if answer:
            answer.emotion_summary = emotion
            session.add(answer)
            session.commit()

def update_session_emotion(session_id: int, emotion: dict):
    with Session(engine) as session:
        interview_session = session.get(InterviewSession, session_id)
        if interview_session:
            interview_session.emotion_summary = emotion
            session.add(interview_session)
            session.commit()
