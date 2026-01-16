from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, Dict, Any
from datetime import datetime

class InterviewSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_name: str
    position: str  # 지원 직무
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="started") # started, completed
    
    # 세션 전체의 감정 통계 (JSONB로 인덱싱 및 정밀 쿼리 가능)
    emotion_summary: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSONB)
    )

class InterviewQuestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="interviewsession.id", index=True)
    question_text: str
    order: int

class InterviewAnswer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="interviewquestion.id", index=True)
    answer_text: str
    
    # Solar-10.7B가 생성한 정밀 평가 JSON 저장
    evaluation: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSONB)
    )
    
    # 해당 답변 구간의 감정 분석 결과 저장
    emotion_summary: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSONB)
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)