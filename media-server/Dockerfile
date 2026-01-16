FROM python:3.10-slim

# 1. WebRTC 및 미디어 처리에 필수적인 시스템 라이브러리 (최적화 유지)
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libavdevice-dev \
    libavfilter-dev \
    libavformat-dev \
    libavcodec-dev \
    libswscale-dev \
    libopus-dev \
    libvpx-dev \
    pkg-config \
    libsrtp2-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. pip 업그레이드
RUN pip install --no-cache-dir --upgrade pip

# 3. 나머지 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 4. 포트 설정 및 실행
EXPOSE 8080
CMD ["python", "main.py"]