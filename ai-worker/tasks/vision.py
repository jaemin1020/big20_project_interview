import base64
import numpy as np
import cv2
import time
import logging
from deepface import DeepFace
from celery import shared_task

logger = logging.getLogger("AI-Worker-Vision")

@shared_task(name="tasks.vision.analyze_emotion")
def analyze_emotion(session_id, base64_img):
    try:
        try:
            session_id = int(session_id)
        except (ValueError, TypeError):
            logger.error(f"Invalid session_id type: {type(session_id)} - {session_id}")
            return {"error": "Invalid session ID format"}
            
        # 이미지 디코딩
        img_data = base64.b64decode(base64_img)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # DeepFace 분석
        results = DeepFace.analyze(
            img_path=img, 
            actions=['emotion'],
            detector_backend='opencv',
            enforce_detection=False
        )
        
        # JSON 결과 구성
        res = {
            "session_id": session_id,
            "dominant_emotion": results[0]['dominant_emotion'],
            "score": results[0]['emotion'][results[0]['dominant_emotion']]
        }
        
        # DB 업데이트 (세션의 최신 감정 상태 업데이트)
        from db import update_session_emotion
        update_session_emotion(session_id, res)
        
        logger.info(f"[{session_id}] Emotion analyzed and saved: {res['dominant_emotion']}")
        return res
    except Exception as e:
        logger.error(f"Vision Task Error: {str(e)}")
        return {"error": str(e)}