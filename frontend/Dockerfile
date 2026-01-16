# 1. Build Stage (Node 18 사용)
FROM node:18-alpine

WORKDIR /app

# 의존성 설치
COPY package.json .
RUN npm install

# 소스 복사
COPY . .

# React 기본 포트
EXPOSE 3000

# 개발 서버 실행
CMD ["npm", "start"]