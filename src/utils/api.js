/**
 * API 유틸리티
 * 백엔드와의 통신을 한 곳에서 관리
 * 각 모듈 컴포넌트는 이 파일만 import하여 API 호출
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000, // 이미지 처리에 시간이 걸릴 수 있으므로 60초
})

// ── 모듈 1: 전처리 ──
export const preprocessAPI = {
  upload: (file, face = 'front', ksize = 5) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/preprocess/upload?face=${face}&ksize=${ksize}`, form)
  },
  getResults: (fileId) => api.get(`/preprocess/results/${fileId}`),
}

// ── 모듈 2: 파노라마 ──
export const panoramaAPI = {
  stitch: (files, face = 'front', method = 'orb') => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    form.append('face', face)
    form.append('method', method)
    return api.post('/panorama/stitch', form)
  },
  stitchPreprocessed: (face = 'front', method = 'orb') => {
    const form = new FormData()
    form.append('face', face)
    form.append('method', method)
    return api.post('/panorama/stitch-preprocessed', form)
  },
}

// ── 모듈 3: 전개도 ──
export const cubenetAPI = {
  // 전처리/파노라마 결과를 자동 탐색하여 전개도 구성 (적응형)
  buildAuto: (showGuides = true) => {
    const form = new FormData()
    form.append('show_guides', showGuides)
    return api.post('/cubenet/build-auto', form)
  },
  // 직접 파일 업로드로 전개도 구성 (fallback)
  build: (faceFiles, faceSize = 512, showGuides = true) => {
    const form = new FormData()
    Object.entries(faceFiles).forEach(([face, file]) => {
      if (file) form.append(face, file)
    })
    form.append('face_size', faceSize)
    form.append('show_guides', showGuides)
    return api.post('/cubenet/build', form)
  },
}

// ── 헬스 체크 ──
export const healthCheck = () => api.get('/health')

// ── 초기화 (이전 결과 삭제) ──
export const resetAll = () => api.post('/reset')

// ── 모듈 4: 3D 뷰어 (Visual Hull) ──
export const viewerAPI = {
  getFaces: () => api.get('/viewer/faces'),
  reconstruct: (resolution = 128, smooth = true) => {
    const form = new FormData()
    form.append('resolution', resolution)
    form.append('smooth', smooth)
    return api.post('/viewer/reconstruct', form)
  },
  getMesh: (meshId) => api.get(`/viewer/mesh/${meshId}`),
  exportObj: () => api.post('/viewer/export-obj'),
}

// ── 모듈 5: Visual Hull 3D 복원 ──
export const reconstructAPI = {
  build: (resolution = 128, smooth = true) => {
    const form = new FormData()
    form.append('resolution', resolution)
    form.append('smooth', smooth)
    return api.post('/reconstruct/build', form)
  },
  getMesh: (modelId) => api.get(`/reconstruct/mesh/${modelId}`),
  getLatest: () => api.get('/reconstruct/latest'),
}

export default api
