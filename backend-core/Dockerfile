# 1. CUDA 런타임이 포함된 이미지를 베이스로 사용 (1660S 호환)
FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# 2. 파이썬 및 시스템 라이브러리 설치
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. pip 업그레이드 및 환경 설정
RUN pip3 install --upgrade pip

# 4. llama-cpp-python을 GPU 가속 모드(CUDA)로 빌드
# 이 설정이 있어야 Llama 모델이 VRAM(6GB)을 사용합니다.
ENV CMAKE_ARGS="-DLLAMA_CUDA=on"
ENV FORCE_CMAKE=1
RUN pip3 install llama-cpp-python --no-cache-dir

# 5. 나머지 라이브러리 설치
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# 6. 실행 (python3 명시)
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]