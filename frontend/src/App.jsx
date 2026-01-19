import { useState, useRef, useEffect } from 'react';
import { createSession, getQuestions, submitAnswer, getResults, login as apiLogin, register as apiRegister, logout as apiLogout, getCurrentUser } from './api/interview';

function App() {
  const [step, setStep] = useState('auth'); // auth, landing, interview, loading, result
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState('login'); // login, register
  const [authError, setAuthError] = useState('');
  
  // Auth 관련 입력 상태
  const [account, setAccount] = useState({ username: '', password: '', fullName: '' });

  const [session, setSession] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [results, setResults] = useState([]);
  
  // STT 관련 상태
  const [transcript, setTranscript] = useState(''); // 현재 질문에 대한 답변 텍스트
  const [isRecording, setIsRecording] = useState(false); // 녹음 상태
  const [fullTranscript, setFullTranscript] = useState(''); // 전체 누적 텍스트
  
  // 사용자 입력 상태
  const [userName, setUserName] = useState('');
  const [position, setPosition] = useState('');
  
  const videoRef = useRef(null);
  const pcRef = useRef(null);
  const wsRef = useRef(null); // WebSocket 참조

  // 유저 정보 확인 로직 추가
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      getCurrentUser()
        .then(u => {
          setUser(u);
          setStep('landing');
          setUserName(u.full_name || u.username);
        })
        .catch(() => {
          localStorage.removeItem('token');
          setStep('auth');
        });
    }
  }, []);

  const handleAuth = async () => {
    setAuthError('');
    try {
      if (authMode === 'login') {
        await apiLogin(account.username, account.password);
        const u = await getCurrentUser();
        setUser(u);
        setUserName(u.full_name || u.username);
        setStep('landing');
      } else {
        await apiRegister(account.username, account.password, account.fullName);
        alert('회원가입 성공! 로그인해주세요.');
        setAuthMode('login');
      }
    } catch (err) {
      setAuthError(err.response?.data?.detail || '인증 실패');
    }
  };

  const handleLogout = () => {
    apiLogout();
    setUser(null);
    setStep('auth');
  };

  const startInterview = async (uName, uPos) => {
    if (!uName.trim() || !uPos.trim()) {
      alert("이름과 지원 직무를 입력해주세요.");
      return;
    }
    console.log(uName, uPos + ' 입력됨');
    try {
      const sess = await createSession(uName, uPos);
      setSession(sess);
      const qs = await getQuestions(sess.id);
      setQuestions(qs);
      setStep('interview');
      // WebRTC 및 WebSocket 연결은 useEffect에서 step이 'interview'로 변경된 후 실행됩니다.
    } catch (err) {
      console.error("Interview start error:", err);
      alert("면접 세션 생성에 실패했습니다. 백엔드 서버 상태를 확인해주세요.");
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

    try {
      // 카메라와 마이크 권한 요청
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      videoRef.current.srcObject = stream;
      stream.getTracks().forEach(track => pc.addTrack(track, stream));
      console.log('[WebRTC] Video and audio tracks added');
    } catch (err) {
      console.warn('[WebRTC] Camera access failed, trying audio-only mode:', err);
      
      try {
        // 카메라 실패 시 오디오만 사용
        const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioStream.getTracks().forEach(track => pc.addTrack(track, audioStream));
        console.log('[WebRTC] Audio-only mode enabled (emotion analysis will be skipped)');
        alert('카메라 접근이 거부되었습니다. 음성 인식만 사용하여 면접을 진행합니다.');
      } catch (audioErr) {
        console.error('[WebRTC] Audio access also failed:', audioErr);
        alert('마이크 접근이 거부되었습니다. 면접을 진행할 수 없습니다.');
        throw audioErr;
      }
    }

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
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
        if (pcRef.current) {
          pcRef.current.close();
          pcRef.current = null;
        }
        
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

  // 면접 단계 진입 시 Media 설정
  useEffect(() => {
    if (step === 'interview' && session && videoRef.current && !pcRef.current) {
      const initMedia = async () => {
        try {
          await setupWebRTC(session.id);
          setupWebSocket(session.id);
        } catch (err) {
          console.error("Media initialization error:", err);
          alert("카메라 및 마이크 연결에 실패했습니다.");
        }
      };
      initMedia();
    }
  }, [step, session]);

  // 컴포넌트 언마운트 시 리소스 정리
  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }
    };
  }, []);
  // start of html
  return (
    <div className="container">
      {step === 'auth' && (
        <div className="card">
          <h1>{authMode === 'login' ? '로그인' : '회원가입'}</h1>
          <div className="input-group" style={{ marginBottom: '20px', display: 'flex', flexDirection: 'column', gap: '10px', textAlign: 'left' }}>
            {authMode === 'register' && (
              <div>
                <label style={{ display: 'block', marginBottom: '5px' }}>성함:</label>
                <input 
                  type="text" 
                  value={account.fullName}
                  onChange={(e) => setAccount({ ...account, fullName: e.target.value })}
                  style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ccc', color: '#333' }}
                />
              </div>
            )}
            <div>
              <label style={{ display: 'block', marginBottom: '5px' }}>아이디:</label>
              <input 
                type="text" 
                value={account.username}
                onChange={(e) => setAccount({ ...account, username: e.target.value })}
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ccc', color: '#333' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '5px' }}>비밀번호:</label>
              <input 
                type="password" 
                value={account.password}
                maxLength={24}
                onChange={(e) => setAccount({ ...account, password: e.target.value })}
                placeholder="최대 24자"
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ccc', color: '#333' }}
              />
            </div>
            {authError && <p style={{ color: '#ef4444', margin: 0 }}>{authError}</p>}
          </div>
          <button onClick={handleAuth} style={{ width: '100%', marginBottom: '10px' }}>
            {authMode === 'login' ? '로그인' : '회원가입'}
          </button>
          <p 
            style={{ cursor: 'pointer', color: '#3b82f6', fontSize: '0.9em' }} 
            onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
          >
            {authMode === 'login' ? '계정이 없으신가요? 회원가입' : '이미 계정이 있으신가요? 로그인'}
          </p>
        </div>
      )}

      {step === 'landing' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h1>AI Interview System</h1>
            <button onClick={handleLogout} style={{ padding: '5px 10px', fontSize: '0.8em', backgroundColor: '#64748b' }}>로그아웃</button>
          </div>
          <p>지원 정보를 입력하고 면접을 시작하세요.</p>
          <div className="input-group" style={{ marginBottom: '20px', display: 'flex', flexDirection: 'column', gap: '10px', textAlign: 'left' }}>
            <div>
              <label htmlFor="name" style={{ display: 'block', marginBottom: '5px' }}>이름:</label>
              <input 
                id="name" 
                type="text" 
                placeholder="이름을 입력하세요" 
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ccc', color: '#333' }}
              />
            </div>
            <div>
              <label htmlFor="position" style={{ display: 'block', marginBottom: '5px' }}>지원 직무:</label>
              <input 
                id="position" 
                type="text" 
                placeholder="지원 직무 (예: Frontend 개발자)" 
                value={position}
                onChange={(e) => setPosition(e.target.value)}
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ccc', color: '#333' }}
              />
            </div>
          </div>
          <button onClick={() => startInterview(userName, position)}>
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
