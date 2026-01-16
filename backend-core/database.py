import os
import time
import logging
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.exc import OperationalError

# 로깅 설정 (프로젝트 원칙 적용)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("Database")

# 환경 변수에서 URL 로드
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:1234@db:5432/interview_db")

# echo=True는 개발 단계에서 SQL 쿼리 로그를 볼 수 있어 유용합니다.
engine = create_engine(
    DATABASE_URL, 
    echo=False, 
    pool_pre_ping=True # 연결이 끊겼는지 미리 확인하는 옵션
)

def init_db():
    """DB 연결 시도 및 테이블 생성 (재시도 로직 포함)"""
    max_retries = 10
    for i in range(max_retries):
        try:
            logger.info(f"데이터베이스 연결 시도 중... ({i+1}/{max_retries})")
            SQLModel.metadata.create_all(engine)
            logger.info("✅ 데이터베이스 테이블 생성 및 연결 성공")
            return
        except OperationalError as e:
            if i < max_retries - 1:
                logger.warning(f"⚠️ DB 연결 실패, 3초 후 재시도합니다... 에러: {e}")
                time.sleep(3)
            else:
                logger.error("❌ DB 연결 실패: 최대 재시도 횟수를 초과했습니다.")
                raise e

def get_session():
    """FastAPI Dependency Injection용 세션 생성기"""
    with Session(engine) as session:
        yield session