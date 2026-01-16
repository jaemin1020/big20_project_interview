import os
import logging
from langchain_huggingface import HuggingFacePipeline
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, BitsAndBytesConfig
import torch

logger = logging.getLogger("Backend-Core-LlamaGen")

# 모델 로드 (HuggingFace Pipeline 사용)
# 실제 환경에서는 모델 경로를 환경 변수나 볼륨 마운트로 관리하는 것이 좋음
MODEL_ID = "meta-llama/Llama-3.2-3B-Instruct"

class QuestionGenerator:
    def __init__(self):
        logger.info(f"Loading Llama model with 4-bit quantization: {MODEL_ID}")
        token=os.getenv("HUGGINGFACE_HUB_TOKEN")
        
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
            max_new_tokens=256,
            temperature=0.7,
            top_p=0.9,
            repetition_penalty=1.1,
            do_sample=True
        )
        self.llm = HuggingFacePipeline(pipeline=pipe)
        
    def generate_questions(self, position: str, count: int = 5):
        prompt = PromptTemplate.from_template(
            """
            ### System:
            당신은 유능한 기술 면접관입니다. {position} 직무에 적합한 실무 면접 질문 {count}개를 작성하세요.
            질문은 한국어로 작성하며, 각 질문은 선언적인 문장으로 명확하게 표현하세요.
            질문 이외의 부가적인 설명은 생략하십시오.

            ### Assistant:
            """
        )
        
        chain = prompt | self.llm | StrOutputParser()
        result = chain.invoke({"position": position, "count": count})
        
        # 간단한 파싱 (줄바꿈 등으로 구분된 질문 리스트 추출)
        questions = [q.strip() for q in result.split("\n") if q.strip()]
        return questions[:count]

# 싱글톤 패턴으로 초기화 (API 실행 시 로드)
generator = QuestionGenerator()
