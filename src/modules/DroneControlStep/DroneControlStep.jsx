import { useState, useEffect } from 'react';
import { PlaneTakeoff, PlaneLanding, ArrowUp, ArrowDown, Camera } from 'lucide-react';

// 노트북에서 실행 중인 브릿지 서버 주소
const BRIDGE_URL = "http://localhost:8001";

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

  // 사진 촬영 및 집 서버로 업로드 명령 함수
  const handleCapture = async () => {
    try {
      alert(`'${targetFace}' 면 캡처 및 서버 업로드 시작...`);
      const res = await fetch(`${BRIDGE_URL}/capture/${targetFace}`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        alert('업로드 완료! 대시보드 전처리 탭을 확인하세요.');
      } else {
        alert('업로드 실패: ' + data.message);
      }
    } catch (e) {
      alert("캡처 요청 실패!");
    }
  };

  // 키보드 조작 지원 (WASD)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'w') sendCommand('forward');
      if (e.key === 's') sendCommand('back');
      if (e.key === 'a') sendCommand('left');
      if (e.key === 'd') sendCommand('right');
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
        
        {/* 브릿지 서버에서 뿌려주는 MJPEG 영상 스트림을 img 태그로 받음 */}
        <img 
          src={`${BRIDGE_URL}/video_feed`} 
          alt="Drone Video Feed" 
          className="w-full h-[500px] object-cover"
          onError={(e) => e.target.src = '/placeholder-drone.jpg'} // 연결 안될 시 대체 이미지
        />
      </div>

      {/* 오른쪽: 조종 패널 */}
      <div className="flex flex-col gap-4">
        <h2 className="text-xl font-bold text-slate-200">드론 관제소</h2>
        
        <div className="grid grid-cols-2 gap-2">
          <button onClick={() => sendCommand('takeoff')} className="bg-emerald-600 hover:bg-emerald-500 py-3 rounded-lg flex justify-center items-center gap-2 font-bold text-white">
            <PlaneTakeoff size={20} /> 이륙
          </button>
          <button onClick={() => sendCommand('land')} className="bg-red-600 hover:bg-red-500 py-3 rounded-lg flex justify-center items-center gap-2 font-bold text-white">
            <PlaneLanding size={20} /> 착륙
          </button>
        </div>

        <div className="bg-slate-800 p-4 rounded-lg mt-4 text-center">
          <p className="text-sm text-slate-400 mb-2">고도 조절</p>
          <div className="flex justify-center gap-4">
            <button onClick={() => sendCommand('up')} className="p-4 bg-slate-700 hover:bg-slate-600 rounded-full text-white"><ArrowUp /></button>
            <button onClick={() => sendCommand('down')} className="p-4 bg-slate-700 hover:bg-slate-600 rounded-full text-white"><ArrowDown /></button>
          </div>
          <p className="text-xs text-slate-500 mt-2">이동은 W A S D 키보드 사용</p>
        </div>

        <div className="mt-auto">
          <select 
            value={targetFace} 
            onChange={(e) => setTargetFace(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 text-white p-3 rounded-lg mb-2"
          >
            <option value="front">전면 (Front)</option>
            <option value="back">후면 (Back)</option>
            <option value="left">좌측 (Left)</option>
            <option value="right">우측 (Right)</option>
            <option value="top">상단 (Top)</option>
          </select>
          <button onClick={handleCapture} className="w-full bg-blue-600 hover:bg-blue-500 py-4 rounded-lg flex justify-center items-center gap-2 font-bold text-white text-lg shadow-lg shadow-blue-900/50">
            <Camera size={24} /> 캡처 및 서버 전송
          </button>
        </div>
      </div>
    </div>
  );
}