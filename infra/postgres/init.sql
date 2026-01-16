CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. 사용자 및 프로필
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) DEFAULT 'candidate',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. 질문 은행 (HuggingFace Embedding)
CREATE TABLE questions (
    question_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(50),
    content TEXT NOT NULL,
    embedding vector(1024), -- BGE-M3 모델 기준
    rubric JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ON questions USING hnsw (embedding vector_cosine_ops);

-- 3. 면접 세션 및 상세 결과
CREATE TABLE interviews (
    interview_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id),
    status VARCHAR(20) DEFAULT 'ready',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE interview_details (
    detail_id SERIAL PRIMARY KEY,
    interview_id UUID REFERENCES interviews(interview_id),
    question_text TEXT,
    answer_text TEXT, -- Deepgram STT
    emotion_label VARCHAR(20), -- DeepFace
    ai_evaluation TEXT, -- HF 70B(CPU)
    scores JSONB, -- 루브릭 점수
    created_at TIMESTAMP DEFAULT NOW()
);