import { useState, useEffect } from 'react';
import { PlaneTakeoff, PlaneLanding, ArrowUp, ArrowDown, Camera } from 'lucide-react';

// 노트북에서 실행 중인 파이썬 브릿지 서버(FastAPI) 주소
// 포트 번호가 메인 서버(8000)와 겹치지 않도록 8001을 사용합니다.
const BRIDGE_URL = "http://172.20.90.95:8001";

export default function DroneControlStep() {
  const [targetFace, setTargetFace] = useState('front');

  // 드론 제어 명령 전송 함수
  const sendCommand = async (cmd) => {
    try {
      await fetch(`${BRIDGE_URL}/command/${cmd}`, { method: 'POST' });
    } catch (e) {
      console.error("명령 전송 실패:", e);
    }
  };

  // 사진 촬영 및 집 서버로 자동 업로드 명령 함수
  const handleCapture = async () => {
    try {
      alert(`'${targetFace}' 면 캡처 및 서버 전송을 시작합니다...`);
      const res = await fetch(`${BRIDGE_URL}/capture/${targetFace}`, { method: 'POST' });
      const data = await res.json();
      
      if (data.status === 'success') {
        alert('업로드 성공! [전처리] 단계 탭에서 사진을 확인하세요.');
      } else {
        alert('업로드 실패: ' + data.message);
      }
    } catch (e) {
      alert("브릿지 서버와 통신할 수 없습니다. (노트북의 파이썬 코드가 실행 중인지 확인하세요)");
    }
  };

  // 키보드 조작 이벤트 리스너 (WASD)
  useEffect(() => {
    const handleKeyDown = (e) => {
      // 입력 폼이나 선택 상자에 포커스가 있을 때는 키보드 조작 무시
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

      if (e.key === 'w' || e.key === 'W') sendCommand('forward');
      if (e.key === 's' || e.key === 'S') sendCommand('back');
      if (e.key === 'a' || e.key === 'A') sendCommand('left');
      if (e.key === 'd' || e.key === 'D') sendCommand('right');
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="p-6 grid grid-cols-3 gap-6">
      {/* 왼쪽: 비디오 스트리밍 영역 */}
      <div className="col-span-2 bg-slate-900 rounded-xl overflow-hidden border border-slate-700 relative">
        <div className="absolute top-4 left-4 bg-black/60 px-3 py-1 rounded text-white font-mono text-sm z-10">
          Target: {targetFace.toUpperCase()}
        </div>
        
        {/* 파이썬 브릿지 서버에서 뿌려주는 MJPEG 영상 스트림을 직접 연결 */}
        <img 
          src={`${BRIDGE_URL}/video_feed`} 
          alt="Drone Video Feed" 
          className="w-full h-[500px] object-cover"
          onError={(e) => {
            // 영상 스트림을 불러오지 못했을 때의 대체(Fallback) UI
            e.target.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 800 500" fill="%230d1520"><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="24" fill="%23475569">드론 카메라 연결 대기 중...</text></svg>';
          }} 
        />
      </div>

      {/* 오른쪽: 조종 및 캡처 패널 */}
      <div className="flex flex-col gap-4">
        <h2 className="text-xl font-bold text-slate-200">웹 관제 시스템</h2>
        
        {/* 이륙 / 착륙 버튼 */}
        <div className="grid grid-cols-2 gap-2">
          <button 
            onClick={() => sendCommand('takeoff')} 
            className="bg-emerald-600 hover:bg-emerald-500 py-3 rounded-lg flex justify-center items-center gap-2 font-bold text-white transition-colors"
          >
            <PlaneTakeoff size={20} /> 이륙
          </button>
          <button 
            onClick={() => sendCommand('land')} 
            className="bg-red-600 hover:bg-red-500 py-3 rounded-lg flex justify-center items-center gap-2 font-bold text-white transition-colors"
          >
            <PlaneLanding size={20} /> 착륙
          </button>
        </div>

        {/* 고도 조절 및 키보드 조작 안내 */}
        <div className="bg-slate-800 p-4 rounded-lg mt-4 text-center border border-slate-700">
          <p className="text-sm text-slate-400 mb-2 font-medium">고도 조절</p>
          <div className="flex justify-center gap-4">
            <button 
              onClick={() => sendCommand('up')} 
              className="p-4 bg-slate-700 hover:bg-slate-600 rounded-full text-white transition-colors"
            >
              <ArrowUp size={24} />
            </button>
            <button 
              onClick={() => sendCommand('down')} 
              className="p-4 bg-slate-700 hover:bg-slate-600 rounded-full text-white transition-colors"
            >
              <ArrowDown size={24} />
            </button>
          </div>
          <p className="text-xs text-slate-500 mt-4">수평 이동은 키보드 <kbd className="bg-slate-900 px-1 rounded">W</kbd> <kbd className="bg-slate-900 px-1 rounded">A</kbd> <kbd className="bg-slate-900 px-1 rounded">S</kbd> <kbd className="bg-slate-900 px-1 rounded">D</kbd> 사용</p>
        </div>

        {/* 타겟 면 선택 및 캡처 업로드 버튼 */}
        <div className="mt-auto pt-4 border-t border-slate-800">
          <select 
            value={targetFace} 
            onChange={(e) => setTargetFace(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 text-slate-200 p-3 rounded-lg mb-3 focus:outline-none focus:border-blue-500 transition-colors"
          >
            <option value="front">전면 (Front)</option>
            <option value="back">후면 (Back)</option>
            <option value="left">좌측 (Left)</option>
            <option value="right">우측 (Right)</option>
            <option value="top">상단 (Top)</option>
          </select>
          <button 
            onClick={handleCapture} 
            className="w-full bg-blue-600 hover:bg-blue-500 py-4 rounded-lg flex justify-center items-center gap-2 font-bold text-white text-lg shadow-lg shadow-blue-900/20 transition-all active:scale-95">
            <Camera size={24} /> 캡처 및 서버 전송
          </button>
        </div>
      </div>
    </div>
  );
}