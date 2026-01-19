import os
import logging
from langchain_huggingface import HuggingFacePipeline
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, BitsAndBytesConfig
import torch

logger = logging.getLogger("Backend-Core-LlamaGen")

# 모델 로드 (HuggingFace Pipeline 사용)
MODEL_ID = "meta-llama/Llama-3.2-3B-Instruct"

class QuestionGenerator:
    def __init__(self):
        logger.info(f"Loading Llama model with 4-bit quantization: {MODEL_ID}")
        token = os.getenv("HUGGINGFACE_HUB_TOKEN")
        
        # BitsAndBytes 4-bit 양자화 설정 (VRAM 사용량: ~4GB로 축소)
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,                    # 4비트 양자화 활성화
            bnb_4bit_compute_dtype=torch.float16, # 연산은 FP16으로 수행
            bnb_4bit_use_double_quant=True,       # 중첩 양자화 (메모리 추가 절감)
            bnb_4bit_quant_type="nf4"             # NormalFloat4 (LLM에 최적화)
        )
        
        logger.info("Initializing tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, token=token)
        
        logger.info("Loading 4-bit quantized model (this may take 1-2 minutes)...")
        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            quantization_config=quantization_config,
            device_map="auto",                    # GPU 자동 할당
            dtype=torch.float16,
            low_cpu_mem_usage=True,               # CPU 메모리 사용 최소화
            token=token
        )
        
        logger.info("✅ Model loaded successfully with 4-bit quantization")
        logger.info(f"📊 Estimated VRAM usage: ~4GB (original: ~16GB)")
        
        # Pipeline 생성
        pipe = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            max_new_tokens=128,  # 질문 하나만 생성하므로 토큰 수 감소
            temperature=0.8,
            top_p=0.9,
            repetition_penalty=1.2,
            do_sample=True
        )
        self.llm = HuggingFacePipeline(pipeline=pipe)
        
    def generate_questions(self, position: str, count: int = 5, previous_qa: list = None):
        """
        면접 질문을 순차적으로 생성합니다.
        
        Args:
            position: 지원 직무 (예: "Frontend 개발자")
            count: 생성할 질문 개수
            previous_qa: 이전 질문-답변 쌍 리스트 [{"question": "...", "answer": "..."}]
        
        Returns:
            list: 생성된 질문 리스트
        """
        questions = []
        
        for i in range(count):
            # 이전 대화 컨텍스트 구성
            context = ""
            if previous_qa and len(previous_qa) > 0:
                context = "\n### 이전 대화:\n"
                for qa in previous_qa[-3:]:  # 최근 3개만 참조
                    context += f"면접관: {qa['question']}\n"
                    context += f"지원자: {qa['answer']}\n"
            
            # 프롬프트 템플릿 (한국어 강제, 면접관 페르소나)
            if i == 0 and not previous_qa:
                # 첫 질문: 직무 관련 기본 질문
                prompt_template = """### 시스템 지시사항:
당신은 {position} 직무의 전문 면접관입니다.
지원자의 실무 역량을 평가하기 위한 질문을 작성하세요.

### 규칙:
1. 반드시 한국어로 작성
2. 질문 하나만 작성 (추가 설명 금지)
3. 실무 중심의 구체적인 질문
4. 질문은 "~해주세요" 또는 "~무엇인가요?" 형식

### 면접관:
"""
            else:
                # 후속 질문: 이전 답변 기반 꼬리질문
                prompt_template = """### 시스템 지시사항:
당신은 {position} 직무의 전문 면접관입니다.
{context}

### 규칙:
1. 반드시 한국어로 작성
2. 질문 하나만 작성 (추가 설명 금지)
3. 이전 답변과 연관된 심화 질문 또는 새로운 각도의 질문
4. 질문은 "~해주세요" 또는 "~무엇인가요?" 형식

### 면접관:
"""
            
            prompt = PromptTemplate.from_template(prompt_template)
            chain = prompt | self.llm | StrOutputParser()
            
            try:
                result = chain.invoke({
                    "position": position,
                    "context": context
                })
                
                # 생성된 텍스트에서 질문 추출 (불필요한 부분 제거)
                question = self._extract_question(result)
                
                if question:
                    questions.append(question)
                    logger.info(f"Generated question {i+1}/{count}: {question}")
                else:
                    # 질문 생성 실패 시 폴백
                    fallback = self._get_fallback_question(position, i)
                    questions.append(fallback)
                    logger.warning(f"Using fallback question {i+1}/{count}")
                    
            except Exception as e:
                logger.error(f"Question generation error: {e}")
                fallback = self._get_fallback_question(position, i)
                questions.append(fallback)
        
        return questions
    
    def _extract_question(self, raw_output: str) -> str:
        """생성된 텍스트에서 실제 질문만 추출"""
        # 줄바꿈으로 분리
        lines = [line.strip() for line in raw_output.split('\n') if line.strip()]
        
        # 가장 긴 문장을 질문으로 간주 (보통 질문이 가장 길음)
        if lines:
            question = max(lines, key=len)
            # "면접관:", "질문:" 등의 접두사 제거
            question = question.replace("면접관:", "").replace("질문:", "").strip()
            return question if len(question) > 10 else ""
        return ""
    
    def _get_fallback_question(self, position: str, index: int) -> str:
        """질문 생성 실패 시 사용할 기본 질문"""
        fallback_questions = [
            f"{position} 직무에 지원하게 된 동기는 무엇인가요?",
            f"{position} 분야에서 가장 자신 있는 기술이나 경험은 무엇인가요?",
            "최근 진행한 프로젝트에 대해 설명해주세요.",
            "기술적 문제를 해결했던 경험을 구체적으로 공유해주세요.",
            "팀 협업 과정에서 어려움을 겪었던 경험과 해결 방법을 말씀해주세요."
        ]
        return fallback_questions[index % len(fallback_questions)]

# 싱글톤 패턴으로 초기화 (API 실행 시 로드)
generator = QuestionGenerator()
