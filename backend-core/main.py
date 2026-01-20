from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from celery import Celery
import logging
# from dotenv import load_dotenv

# load_dotenv()

from database import engine, init_db, get_session
from models import InterviewSession, InterviewRecord, User, SessionCreate
from chains.llama_gen import generator
from auth import get_password_hash, verify_password, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta, datetime

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
    allow_origins=["http://localhost:3000"],
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

@app.post("/register")
async def register(user: User, db: Session = Depends(get_session)):
    # Check if user exists
    statement = select(User).where(User.username == user.username)
    db_user = db.exec(statement).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    user.hashed_password = get_password_hash(user.hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"username": user.username, "id": user.id}

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_session)):
    statement = select(User).where(User.username == form_data.username)
    user = db.exec(statement).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/sessions", response_model=InterviewSession)
async def create_session(
    session_data: SessionCreate, 
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # SessionCreate 데이터를 바탕으로 InterviewSession 생성
    new_session = InterviewSession(
        user_id=current_user.id,
        user_name=session_data.user_name,
        position=session_data.position
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    logger.info(f"Created session with ID: {new_session.id}")
    
    # 질문 생성 로직
    try:
        logger.info(f"Generating AI questions for position: {new_session.position}")
        generated_questions = generator.generate_questions(
            position=new_session.position,
            count=5,
        )
        logger.info(f"Generated {len(generated_questions)} questions successfully")
    except Exception as e:
        logger.error(f"Question generation failed: {str(e)}, using fallback questions")
        generated_questions = [
            f"{new_session.position} 직무의 핵심 역량은 무엇인가요?",
            "최근 진행한 프로젝트에 대해 설명해주세요.",
            "기술적 문제를 해결한 경험을 공유해주세요."
        ]
    
    # DB에 InterviewRecord 형태로 저장
    for i, q_text in enumerate(generated_questions):
        record = InterviewRecord(
            session_id=new_session.id,
            question_text=q_text,
            order=i + 1
        )
        db.add(record)
    
    db.commit()
    db.refresh(new_session)
    return new_session

@app.get("/sessions/{session_id}/questions", response_model=list[InterviewRecord])
async def get_questions(
    session_id: int, 
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    statement = select(InterviewRecord).where(InterviewRecord.session_id == session_id).order_by(InterviewRecord.order)
    results = db.exec(statement).all()
    return results

@app.post("/answers")
async def submit_answer(
    # record_id와 answer_text만 받으면 됨
    answer_data: Dict[str, Any], 
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    record_id = answer_data.get("record_id")
    answer_text = answer_data.get("answer_text")
    
    # 1. 기존 레코드 조회
    record = db.get(InterviewRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Interview record not found")
        
    # 2. 답변 내용 업데이트
    record.answer_text = answer_text
    record.answered_at = datetime.utcnow()
    db.add(record)
    db.commit()
    db.refresh(record)
    
    # 3. ai-worker에 정밀 평가 요청 전달
    celery_app.send_task(
        "tasks.evaluator.analyze_answer",
        args=[
            record.id, 
            record.question_text,
            record.answer_text,
            "기술적 정확성, 논리적 구성, 전문 용어 사용 적절성"
        ]
    )
    
    return {"status": "submitted", "record_id": record.id}

@app.get("/sessions/{session_id}/results")
async def get_session_results(
    session_id: int, 
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    statement = select(InterviewRecord).where(InterviewRecord.session_id == session_id).order_by(InterviewRecord.order)
    results = db.exec(statement).all()
    
    return [
        {
            "question": r.question_text,
            "answer": r.answer_text,
            "evaluation": r.evaluation,
            "emotion": r.emotion_summary
        }
        for r in results
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)