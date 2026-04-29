/**
 * 공유 상수
 * 면 이름, 파이프라인 단계 등 프로젝트 전역에서 사용하는 값
 */

export const FACES = ['front', 'back', 'left', 'right', 'top']

export const FACE_LABELS = {
  front: '전면',
  back: '후면',
  left: '좌측',
  right: '우측',
  top: '상단',
}

export const PIPELINE_STEPS = [
  { id: 'control', label: '드론 관제', icon: 'Gamepad2' },
  { id: 'upload', label: '이미지 업로드', icon: 'Upload' },
  { id: 'preprocess', label: '전처리', icon: 'ScanLine' },
  { id: 'panorama', label: '파노라마 합성', icon: 'Images' },
  { id: 'cubenet', label: '전개도 구성', icon: 'Box' },
  { id: 'viewer', label: '3D 복원', icon: 'Rotate3D' },
]
