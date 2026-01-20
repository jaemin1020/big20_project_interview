from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, Dict, Any
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    full_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SessionCreate(SQLModel):
    user_name: str
    position: str

class InterviewSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    user_name: str
    position: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="started") # started, completed
    
    emotion_summary: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSONB)
    )

class InterviewRecord(SQLModel, table=True):
    """질문과 답변을 하나의 테이블에서 관리"""
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="interviewsession.id", index=True)
    
    # 질문 관련
    question_text: str
    order: int
    
    # 답변 관련 (초기에는 None)
    answer_text: Optional[str] = None
    
    # 태스크 결과 (Solar LLM 평가 및 감정 분석)
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