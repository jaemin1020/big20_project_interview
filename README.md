## 1. 프로젝트 폴더 구조

big20_project_env_set/
├── .env                        # 공통 환경 변수 (API 키, DB 접속 정보)
├── docker-compose.yml          # 전체 서비스 오케스트레이션 (포트 및 네트워크 설정)
│
├── backend-core/               # [FastAPI] 실시간 질문 생성 (GPU 사용: Llama-3.1-8B Q4)
│   ├── main.py                 # API 라우팅, Celery 태스크 발행
│   ├── database.py             # PostgreSQL & SQLAlchemy 설정
│   ├── models.py               # DB 테이블 정의 (JSONB 타입 포함)
│   ├── chains/
│   │   └── llama_gen.py        # GPU 가속 질문 생성 로직
│   ├── logs/                   # 백엔드 서비스 로그 저장
│   ├── Dockerfile
│   └── requirements.txt
│
├── ai-worker/                  # [Celery] 정밀 평가 및 감정 분석 (CPU/RAM 사용: Solar-10.7B Q8)
│   ├── main.py                 # Celery Worker 실행부 (app = Celery)
│   ├── tasks/
│   │   ├── evaluator.py        # LangChain JsonOutputParser 기반 정밀 평가
│   │   └── vision.py           # DeepFace 기반 감정 분석 로직
│   ├── models/                 # 모델 파일 저장 (Volume Mount 권장)
│   │   └── solar-10.7b-instruct-v1.0.Q8_0.gguf
│   ├── logs/                   # 분석 워커 상세 로그 저장
│   ├── Dockerfile
│   └── requirements.txt
│
├── media-server/               # [WebRTC] 음성(STT) 및 영상(프레임 추출) 서버
│   ├── main.py                 # aiortc & Deepgram(Nova-2) 연동
│   ├── logs/                   # 스트리밍 및 미디어 처리 로그
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                   # [React/Vite] 웹 인터페이스
│   ├── src/
│   │   ├── components/         # WebRTC 비디오 핸들러 및 채팅 UI
│   │   └── api/                # Backend-core 연동 로직
│   ├── Dockerfile
│   └── package.json
│
└── infra/                      # 인프라 데이터 저장소
    ├── postgres/               # DB 데이터 영구 저장 (Volume)
    └── redis/                  # Celery 메시지 브로커 데이터

## 2. 프로젝트 실행 (Workflow)

이 프로젝트는 Docker Compose를 사용하여 간편하게 실행할 수 있습니다. 
자세한 단계는 `.agent/workflows/setup-project.md`를 참고하거나 다음 명령어를 실행하세요:

1. `docker-compose build`
2. `docker-compose up -d`

## 3. 핵심 구현 내용 (Technical Implementation)

### 🔹 Backend-Core (FastAPI)
- **RESTful API**: 면접 세션 관리, 질문 조회, 답변 제출 엔드포인트 구현.
- **ORM (SQLModel)**: PostgreSQL 연동을 통한 데이터 영속성 관리 (InterviewSession, Question, Answer).
- **LLM Integration**: Llama-3.1-8B 기반의 직무 맞춤형 실시간 면접 질문 생성 로직 (HuggingFace Pipeline).
- **Task Broker**: Celery를 통해 정밀 평가 및 감정 분석 작업을 비동기적으로 Worker에 전달.

### 🔹 AI-Worker (Celery & LangChain)
- **정밀 평가 (Evaluator)**: Solar-10.7B 모델과 LangChain `JsonOutputParser`를 활용한 기술적 피드백 생성.
- **시각 분석 (Vision)**: `DeepFace` 모델을 사용하여 수신된 영상 프레임에서 사용자 감정(Emotion) 추출.
- **Async DB Update**: 분석이 완료된 결과는 워커 프로세스에서 직접 DB에 반영하여 실시간성 확보.

### 🔹 Media-Server (WebRTC & STT)
- **Real-time Streaming**: `aiortc` 라이브러리를 사용해 프론트엔드와 WebRTC 연결 및 미디어 트랙 처리.
- **Frame Extraction**: CPU 부하 최적화를 위해 2초 간격으로 비디오 프레임을 추출하여 AI-Worker로 전달.
- **STT**: Deepgram SDK(Nova-2 모델)를 통한 음성-텍스트 실시간 변환 기반 마련.

### 🔹 Frontend (React & Vite)
- **Glassmorphism UI**: 프리미엄 다크 모드 테마와 반응형 레이아웃 적용.
- **Interview Flow**: 면접 시작 -> 질문 대기 -> 실시간 답변/분석 -> 최종 리포트 대시보드 구현.
- **WebRTC Client**: 브라우저 카메라/마이크 권한 획득 및 미디어 서버와의 P2P 통신 연동.

## 4. 모델 성능 및 사양

| 역할 | 모델 명 | 양자화(Format) | 가동 자원 | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **실시간 질문** | Llama-3.1-8B | FP16/GGUF Q4 | GPU (VRAM 5GB+) | 빠른 반응성 중심 |
| **정밀 평가** | Solar-10.7B | GGUF (Q8_0) | CPU + RAM (12GB) | 높은 평가 정확도 |
| **감정 분석** | DeepFace (VGG) | - | CPU | 실시간 프레임 분석 |
| **음성 인식** | Deepgram Nova-2 | Cloud API | Network | 한국어 최적화 |