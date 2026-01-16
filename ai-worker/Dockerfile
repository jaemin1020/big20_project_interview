FROM python:3.10-slim

# 1. DeepFace(OpenCV) 및 Llama-cpp 빌드를 위한 필수 라이브러리 수정
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. 의존성 설치
COPY requirements.txt .

# CPU 최적화 옵션과 함께 설치
RUN CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS" pip install llama-cpp-python
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# JSON 로그 및 모듈 경로 설정
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["celery", "-A", "main.app", "worker", "--loglevel=info"]