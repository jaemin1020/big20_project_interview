import { useState, useRef, useEffect } from 'react';
import { createSession, getQuestions, submitAnswer, getResults } from './api/interview';

function App() {
  const [step, setStep] = useState('landing');
  const [session, setSession] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [results, setResults] = useState([]);
  
  // STT 관련 상태
  const [transcript, setTranscript] = useState(''); // 현재 질문에 대한 답변 텍스트
  const [isRecording, setIsRecording] = useState(false); // 녹음 상태
  const [fullTranscript, setFullTranscript] = useState(''); // 전체 누적 텍스트
  
  const videoRef = useRef(null);
  const pcRef = useRef(null);
  const wsRef = useRef(null); // WebSocket 참조

  const startInterview = async (userName, position) => {
    try {
      const sess = await createSession(userName, position);
      setSession(sess);
      const qs = await getQuestions(sess.id);
      setQuestions(qs);
      setStep('interview');
      await setupWebRTC(sess.id);
      setupWebSocket(sess.id); // WebSocket 연결 추가
    } catch (err) {
      console.error("Interview start error:", err);
      alert("Failed to start session. Make sure backend is running.");
    }
  };

  const setupWebSocket = (sessionId) => {
    // WebSocket으로 media-server와 연결 (STT 결과 수신용)
    const ws = new WebSocket(`ws://localhost:8080/ws/${sessionId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WebSocket] Connected to media server for STT');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'stt_result' && data.text) {
          // 실시간 STT 결과를 현재 transcript에 추가
          setTranscript(prev => prev + ' ' + data.text);
          setFullTranscript(prev => prev + ' ' + data.text);
          console.log('[STT]:', data.text);
        }
      } catch (err) {
        console.error('[WebSocket] Parse error:', err);
      }
    };

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
    };

    ws.onclose = () => {
      console.log('[WebSocket] Connection closed');
    };
  };

  const setupWebRTC = async (sessionId) => {
    const pc = new RTCPeerConnection();
    pcRef.current = pc;

    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    videoRef.current.srcObject = stream;
    stream.getTracks().forEach(track => pc.addTrack(track, stream));

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    const response = await fetch('http://localhost:8080/offer', {
      method: 'POST',
      body: JSON.stringify({
        sdp: pc.localDescription.sdp,
        type: pc.localDescription.type,
        session_id: sessionId
      }),
      headers: { 'Content-Type': 'application/json' }
    });

    const answer = await response.json();
    await pc.setRemoteDescription(new RTCSessionDescription(answer));
  };

  // 녹음 시작/중지
  const toggleRecording = () => {
    if (isRecording) {
      // 녹음 중지
      setIsRecording(false);
      console.log('[Recording] Stopped');
    } else {
      // 녹음 시작 (새 질문 시작 시 기존 텍스트 초기화)
      setTranscript('');
      setIsRecording(true);
      console.log('[Recording] Started');
    }
  };

  const nextQuestion = async () => {
    // STT로 받아온 실제 텍스트를 제출
    const answerText = transcript.trim() || "답변 내용 없음 (음성 인식 실패 또는 무응답)";
    
    try {
      await submitAnswer(questions[currentIdx].id, answerText);
      console.log(`[Submit] Question ${currentIdx + 1} answered:`, answerText);
      
      // 다음 질문으로 이동 또는 종료
      if (currentIdx < questions.length - 1) {
        setCurrentIdx(currentIdx + 1);
        setTranscript(''); // 다음 질문을 위해 텍스트 초기화
        setIsRecording(false); // 녹음 상태 리셋
      } else {
        // 면접 종료
        setStep('loading');
        
        // WebSocket 및 WebRTC 연결 종료
        if (wsRef.current) wsRef.current.close();
        if (pcRef.current) pcRef.current.close();
        
        // AI 평가 완료 대기 후 결과 조회
        setTimeout(async () => {
          const res = await getResults(session.id);
          setResults(res);
          setStep('result');
        }, 8000); // AI 평가 처리 시간 (Solar 모델 추론 시간 고려)
      }
    } catch (err) {
      console.error('[Submit Error]:', err);
      alert('답변 제출에 실패했습니다. 다시 시도해주세요.');
    }
  };

  // 컴포넌트 언마운트 시 리소스 정리
  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (pcRef.current) pcRef.current.close();
    };
  }, []);

  return (
    <div className="container">
      {step === 'landing' && (
        <div className="card">
          <h1>AI Interview System</h1>
          <p>지원 정보를 입력하고 면접을 시작하세요.</p>
          <button onClick={() => startInterview("홍길동", "Frontend Engineer")}>
            면접 시작하기
          </button>
        </div>
      )}

      {step === 'interview' && (
        <div className="card">
          <h2>실시간 면접 중</h2>
          <video ref={videoRef} autoPlay playsInline muted />
          
          {questions.length > 0 && (
            <div className="question-box">
              <h3>질문 {currentIdx + 1}:</h3>
              <p>{questions[currentIdx].question_text}</p>
              
              {/* 실시간 STT 전사 텍스트 표시 */}
              <div style={{ 
                marginTop: '15px', 
                padding: '10px', 
                background: 'rgba(16, 185, 129, 0.1)', 
                borderRadius: '8px',
                minHeight: '60px'
              }}>
                <h4 style={{ color: '#10b981', margin: '0 0 8px 0', fontSize: '0.9em' }}>
                  🎤 {isRecording ? '녹음 중...' : '답변 준비'}
                </h4>
                <p style={{ margin: 0, fontSize: '0.95em', lineHeight: '1.5' }}>
                  {transcript || '답변을 시작하려면 "녹음 시작" 버튼을 눌러주세요.'}
                </p>
              </div>
            </div>
          )}
          
          <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginTop: '15px' }}>
            <button 
              onClick={toggleRecording}
              style={{ 
                backgroundColor: isRecording ? '#ef4444' : '#10b981',
                minWidth: '120px'
              }}
            >
              {isRecording ? '⏸ 녹음 중지' : '🎤 녹음 시작'}
            </button>
            
            <button 
              onClick={nextQuestion}
              disabled={!transcript.trim() && isRecording}
              style={{ 
                opacity: (!transcript.trim() && isRecording) ? 0.5 : 1,
                minWidth: '120px'
              }}
            >
              {currentIdx < questions.length - 1 ? "다음 질문 ➡️" : "면접 종료 ✓"}
            </button>
          </div>
        </div>
      )}

      {step === 'loading' && (
        <div className="card">
          <h2>AI가 답변을 평가 중입니다...</h2>
          <div className="spinner"></div>
          <p>잠시만 기다려 주세요.</p>
        </div>
      )}

      {step === 'result' && (
        <div className="card">
          <h2>면접 결과 분석</h2>
          {results.map((r, i) => (
            <div key={i} className="question-box" style={{ marginBottom: '20px' }}>
              <strong>Q: {r.question}</strong>
              <p>A: {r.answer}</p>
              <div style={{ background: '#1e293b', padding: '10px', borderRadius: '8px', marginTop: '10px' }}>
                <h4 style={{ color: '#3b82f6', margin: '0 0 10px 0' }}>AI 피드백:</h4>
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.9em' }}>
                  {JSON.stringify(r.evaluation, null, 2)}
                </pre>
                <h4 style={{ color: '#10b981', margin: '10px 0' }}>감정 분석:</h4>
                <p>{r.emotion ? `주요 감정: ${r.emotion.dominant_emotion}` : "분석 대기 중..."}</p>
              </div>
            </div>
          ))}
          <button onClick={() => setStep('landing')}>처음으로</button>
        </div>
      )}
    </div>
  );
}

export default App;
