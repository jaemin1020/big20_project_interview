import asyncio
import json
import logging
import os
import base64
import time
import cv2
from typing import Dict, Set
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaRelay
from celery import Celery

# 1. 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("Media-Server")

app = FastAPI()
relay = MediaRelay()

# 2. Celery 설정 (ai-worker로 감정 분석 요청 전달용)
celery_app = Celery("ai_worker", broker="redis://redis:6379/0", backend="redis://redis:6379/0")

# 3. WebSocket 연결 관리 (세션별 WebSocket 저장)
active_websockets: Dict[str, WebSocket] = {}

# 4. Deepgram 설정 (STT가 활성화된 경우에만)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
USE_DEEPGRAM = bool(DEEPGRAM_API_KEY)

if USE_DEEPGRAM:
    try:
        # Deepgram SDK 5.3.1 올바른 import
        from deepgram import AsyncDeepgramClient
        from deepgram.core.events import EventType
        logger.info("✅ Deepgram SDK loaded successfully")
    except ImportError as e:
        logger.warning(f"⚠️ Deepgram SDK import error: {e}. STT will be disabled.")
        USE_DEEPGRAM = False
    except Exception as e:
        logger.warning(f"⚠️ Error loading Deepgram SDK: {e}. STT will be disabled.")
        USE_DEEPGRAM = False
else:
    logger.warning("⚠️ DEEPGRAM_API_KEY not set. STT will be disabled.")

class VideoAnalysisTrack(MediaStreamTrack):
    """비디오 프레임을 추출하여 ai-worker에 감정 분석을 요청하는 트랙"""
    kind = "video"

    def __init__(self, track, session_id):
        super().__init__()
        self.track = track
        self.session_id = session_id
        self.last_frame_time = 0

    async def recv(self):
        frame = await self.track.recv()
        current_time = time.time()

        # 2초마다 한 번씩 프레임 추출 (CPU 부하 방지 및 4650G 최적화)
        if current_time - self.last_frame_time > 2.0:
            self.last_frame_time = current_time
            
            # 프레임을 이미지로 변환
            img = frame.to_ndarray(format="bgr24")
            _, buffer = cv2.imencode('.jpg', img)
            base64_img = base64.b64encode(buffer).decode('utf-8')

            # ai-worker에 비동기 감정 분석 태스크 전달 (JSON 포맷 데이터)
            celery_app.send_task(
                "tasks.vision.analyze_emotion",
                args=[self.session_id, base64_img]
            )
            logger.info(f"[{self.session_id}] 감정 분석 프레임 전송 완료")

        return frame

async def start_stt_with_deepgram(audio_track: MediaStreamTrack, session_id: str):
    """Deepgram 실시간 STT 실행 및 WebSocket으로 결과 전송 (SDK v5.3.1 대응)"""
    if not USE_DEEPGRAM:
        logger.warning(f"[{session_id}] Deepgram 비활성화 상태. STT 건너뜀.")
        return
    
    try:
        # Deepgram 비동기 클라이언트 초기화 (SDK 5.x)
        deepgram = AsyncDeepgramClient(api_key=DEEPGRAM_API_KEY)
        
        # 연결 설정 (v2 API 사용, async context manager)
        async with deepgram.listen.v2.connect(
            model="nova-2",
            language="ko",
            smart_format=True,
            encoding="linear16",
            sample_rate=16000,
            channels=1
        ) as dg_connection:
            
            logger.info(f"[{session_id}] Deepgram STT 연결 시작됨")
            
            # 이벤트 핸들러 정의
            async def on_message(message):
                """실시간으로 전송된 텍스트 처리"""
                try:
                    # MESSAGE 이벤트에서 transcript 추출
                    if hasattr(message, 'channel') and message.channel:
                        alternatives = message.channel.alternatives
                        if alternatives and len(alternatives) > 0:
                            transcript = alternatives[0].transcript
                            if transcript:
                                stt_data = {
                                    "session_id": session_id,
                                    "text": transcript,
                                    "type": "stt_result",
                                    "timestamp": time.time()
                                }
                                logger.info(f"[{session_id}] STT: {transcript}")
                                
                                # WebSocket으로 프론트엔드에 실시간 전송
                                if session_id in active_websockets:
                                    ws = active_websockets[session_id]
                                    await send_to_websocket(ws, stt_data)
                except Exception as e:
                    logger.error(f"[{session_id}] on_message 처리 에러: {e}")

            async def on_error(error):
                logger.error(f"[{session_id}] Deepgram 에러: {error}")
            
            async def on_open():
                logger.info(f"[{session_id}] Deepgram WebSocket 열림")
            
            async def on_close():
                logger.info(f"[{session_id}] Deepgram WebSocket 닫힘")

            # 이벤트 핸들러 등록 (SDK 5.x 방식)
            dg_connection.on(EventType.MESSAGE, on_message)
            dg_connection.on(EventType.ERROR, on_error)
            dg_connection.on(EventType.OPEN, on_open)
            dg_connection.on(EventType.CLOSE, on_close)
            
            # listening 시작
            await dg_connection.start_listening()
            
            try:
                # 오디오 트랙에서 프레임 수신 및 전송
                while True:
                    try:
                        frame = await audio_track.recv()
                        
                        # 프레임을 ndarray로 변환 후 바이트로 추출하여 Deepgram으로 전송
                        audio_data = frame.to_ndarray().tobytes()
                        await dg_connection.send(audio_data)
                        
                    except Exception as e:
                        logger.debug(f"[{session_id}] Audio track recv 에러: {e}")
                        break
                        
            except Exception as e:
                logger.error(f"[{session_id}] STT 오디오 처리 에러: {e}")
            finally:
                # 연결 종료
                try:
                    await dg_connection.finish()
                except:
                    pass
                logger.info(f"[{session_id}] Deepgram STT 종료됨")

    except Exception as e:
        logger.error(f"[{session_id}] STT 실행 중 치명적 에러: {str(e)}")

async def send_to_websocket(ws: WebSocket, data: dict):
    """WebSocket으로 데이터 전송 (에러 처리 포함)"""
    try:
        await ws.send_json(data)
    except Exception as e:
        logger.error(f"WebSocket 전송 실패: {e}")

# ============== WebSocket 엔드포인트 ==============
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """프론트엔드와 실시간 STT 결과 공유를 위한 WebSocket 연결"""
    await websocket.accept()
    active_websockets[session_id] = websocket
    logger.info(f"[{session_id}] ✅ WebSocket 연결 성공")
    
    try:
        # 연결 유지 및 클라이언트로부터 메시지 수신 대기
        while True:
            data = await websocket.receive_text()
            # 필요 시 클라이언트로부터 받은 메시지 처리
            logger.debug(f"[{session_id}] Received from client: {data}")
            
    except WebSocketDisconnect:
        logger.info(f"[{session_id}] ❌ WebSocket 연결 종료")
    except Exception as e:
        logger.error(f"[{session_id}] WebSocket 에러: {e}")
    finally:
        # 연결 종료 시 세션 제거
        if session_id in active_websockets:
            del active_websockets[session_id]
            logger.info(f"[{session_id}] WebSocket 세션 정리 완료")

# ============== WebRTC 엔드포인트 ==============
@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    session_id = params.get("session_id", "unknown")

    pc = RTCPeerConnection()
    logger.info(f"[{session_id}] WebRTC 연결 시도")

    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            asyncio.ensure_future(start_stt_with_deepgram(track, session_id))
        elif track.kind == "video":
            pc.addTrack(VideoAnalysisTrack(relay.subscribe(track), session_id))

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }

@app.get("/")
async def root():
    return {
        "service": "AI Interview Media Server",
        "status": "running",
        "websocket_endpoint": "/ws/{session_id}",
        "webrtc_endpoint": "/offer",
        "deepgram_enabled": USE_DEEPGRAM
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")