import logging
import time
import json

from celery import shared_task
from langchain_community.llms import LlamaCpp
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field

from db import update_answer_evaluation
# 1. 로깅 설정
logger = logging.getLogger("AI-Worker-Evaluator")

# 2. 출력 스키마 정의 (Pydantic)
class EvaluationResult(BaseModel):
    technical_score: int = Field(description="기술적 답변의 정확도 (1-5점)")
    communication_score: int = Field(description="전달력 및 논리력 (1-5점)")
    strengths: str = Field(description="답변에서 칭찬할 만한 점")
    weaknesses: str = Field(description="답변에서 보완이 필요한 점")
    total_feedback: str = Field(description="전체 종합 평가 의견")

# 3. 모델 및 파서 초기화 (전역 변수로 선언하여 Worker 시작 시 1회 로드)
MODEL_PATH = "/app/models/solar-10.7b-instruct-v1.0.Q8_0.gguf"
parser = JsonOutputParser(pydantic_object=EvaluationResult)

logger.info(f"Loading Solar-10.7B model on RAM: {MODEL_PATH}")

try:
    eval_llm = LlamaCpp(
        model_path=MODEL_PATH,
        n_ctx=4096,
        n_threads=8,     # Ryzen 4650G의 12스레드 중 8개 사용
        n_gpu_layers=0,  # CPU/RAM 전용 (GPU는 Backend-core가 선점)
        temperature=0.1, # 일관된 JSON 출력을 위해 낮은 온도로 고정
        verbose=False
    )
    logger.info("Solar-10.7B model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load Solar model: {str(e)}")
    raise

@shared_task(name="tasks.evaluator.analyze_answer")
def analyze_answer(session_id, question, user_answer, rubric):
    """
    사용자의 답변을 Solar-10.7B로 정밀 평가하여 JSON 결과를 반환합니다.
    """
    logger.info(f"[{session_id}] 정밀 평가 작업 수신")
    start_time = time.time()

    # 파서가 요구하는 JSON 포맷 가이드를 자동으로 프롬프트에 추가
    format_instructions = parser.get_format_instructions()
    
    prompt = f"""
        ### System:
        당신은 IT 전문 기술 면접관입니다. 아래 질문에 대한 사용자의 답변을 정밀하게 평가하세요.
        반드시 제공된 JSON 포맷 형식을 준수하여 답변해야 합니다.

        ### User:
        면접 질문: {question}
        사용자 답변: {user_answer}
        평가 루브릭: {rubric}

        {format_instructions}

        ### Assistant:
    """

    try:
        # 1. LLM 추론
        raw_output = eval_llm.invoke(prompt)
        
        # 2. LangChain 파서로 JSON 정제
        # (Solar가 서술형 답변을 덧붙여도 JSON 부분만 정확히 추출합니다.)
        parsed_data = parser.parse(raw_output)
        
        # 3. 메타데이터 추가
        parsed_data["session_id"] = session_id
        parsed_data["model"] = "Solar-10.7B-instruct-v1.0-Q8"
        
        # 4. DB 업데이트 (추가됨)
        update_answer_evaluation(session_id, parsed_data) # 여기서 session_id는 answer_id로 전달됨
        
        duration = time.time() - start_time
        logger.info(f"[{session_id}] 평가 완료 및 DB 저장 완료 (소요시간: {duration:.2f}초)")
        
        # 최종 결과 JSON 출력 (로그 확인용)
        logger.info(f"Result: {json.dumps(parsed_data, ensure_ascii=False)}")
        
        return parsed_data

    except Exception as e:
        logger.error(f"[{session_id}] 평가 중 오류 발생: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "session_id": session_id,
            "message": "Evaluation failed during parsing"
        }