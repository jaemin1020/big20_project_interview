from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from celery import Celery
import logging

from database import engine, init_db, get_session
from models import InterviewSession, InterviewQuestion, InterviewAnswer
from chains.llama_gen import generator

# 1. 로깅 및 앱 초기화
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Backend-Core")

app = FastAPI(title="AI Interview Backend")

# DB 초기화
@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Database initialized.")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Celery 설정 (ai-worker 통신용)
celery_app = Celery("ai_worker", broker="redis://redis:6379/0", backend="redis://redis:6379/0")

# 3. API 엔드포인트

@app.get("/")
async def root():
    return {"message": "AI Interview Backend API is running"}

@app.post("/sessions", response_model=InterviewSession)
async def create_session(session_data: InterviewSession, db: Session = Depends(get_session)):
    db.add(session_data)
    db.commit()
    db.refresh(session_data)
    
    # Llama-3.1-8B를 사용하여 직무 맞춤형 질문 생성 (GPU 가속)
    try:
        logger.info(f"Generating AI questions for position: {session_data.position}")
        generated_questions = generator.generate_questions(
            position=session_data.position,
            count=5  # 기본 5개 질문 생성
        )
        logger.info(f"Generated {len(generated_questions)} questions successfully")
    except Exception as e:
        logger.error(f"Question generation failed: {str(e)}, using fallback questions")
        # 생성 실패 시 기본 질문 사용 (Fallback)
        generated_questions = [
            f"{session_data.position} 직무의 핵심 역량은 무엇인가요?",
            "최근 진행한 프로젝트에 대해 설명해주세요.",
            "기술적 문제를 해결한 경험을 공유해주세요."
        ]
    
    # DB에 질문 저장
    for i, q_text in enumerate(generated_questions):
        question = InterviewQuestion(
            session_id=session_data.id,
            question_text=q_text,
            order=i + 1
        )
        db.add(question)
    
    db.commit()
    return session_data

@app.get("/sessions/{session_id}/questions", response_model=list[InterviewQuestion])
async def get_questions(session_id: int, db: Session = Depends(get_session)):
    statement = select(InterviewQuestion).where(InterviewQuestion.session_id == session_id).order_by(InterviewQuestion.order)
    results = db.exec(statement).all()
    return results

@app.post("/answers")
async def submit_answer(answer: InterviewAnswer, db: Session = Depends(get_session)):
    # 1. 답변 저장
    db.add(answer)
    db.commit()
    db.refresh(answer)
    
    # 2. 질문 내용 조회 (평가를 위해)
    question = db.get(InterviewQuestion, answer.question_id)
    
    # 3. ai-worker에 정밀 평가 요청 전달
    celery_app.send_task(
        "tasks.evaluator.analyze_answer",
        args=[
            answer.id, # session_id 대신 answer.id를 넘겨 추후 매칭
            question.question_text,
            answer.answer_text,
            "기술적 정확성, 논리적 구성, 전문 용어 사용 적절성"
        ]
    )
    
    return {"status": "submitted", "answer_id": answer.id}

@app.get("/sessions/{session_id}/results")
async def get_session_results(session_id: int, db: Session = Depends(get_session)):
    # 세션에 속한 모든 질문과 답변 조회
    statement = select(InterviewQuestion, InterviewAnswer).join(
        InterviewAnswer, InterviewQuestion.id == InterviewAnswer.question_id
    ).where(InterviewQuestion.session_id == session_id)
    
    results = db.exec(statement).all()
    
    return [
        {
            "question": q.question_text,
            "answer": a.answer_text,
            "evaluation": a.evaluation,
            "emotion": a.emotion_summary
        }
        for q, a in results
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)