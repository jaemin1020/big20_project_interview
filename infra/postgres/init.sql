-- 1. 필요한 확장 모듈 설치 (AI 기능용)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 테이블 생성은 backend-core의 models.py를 기준으로 SQLModel이 자동 수행합니다.
-- /init.sql은 확장 설정 및 초기 DB 환경 세팅에만 활용됩니다.