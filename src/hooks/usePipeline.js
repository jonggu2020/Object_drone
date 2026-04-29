/**
 * 파이프라인 상태 관리 훅
 * 각 단계의 데이터를 중앙에서 관리하되,
 * 컴포넌트 간 직접 의존은 없도록 설계
 */
import { useState, useCallback } from 'react'

const initialState = {
  // 업로드된 원본 파일 (면별)
  uploadedFiles: {},   // { front: [File, ...], back: [...], ... }

  // 전처리 결과 (면별)
  preprocessed: {},    // { front: { outputs: {...}, contour_found: bool }, ... }

  // 파노라마 결과 (면별)
  panoramas: {},       // { front: { panorama_url: "..." }, ... }

  // 전개도 결과
  cubenet: null,       // { net_url: "...", faces_used: [...] }

  // 현재 활성 단계
  activeStep: 'control',

  // 로딩 상태
  loading: false,
  error: null,
}

export default function usePipeline() {
  const [state, setState] = useState(initialState)

  const setLoading = useCallback((loading, error = null) => {
    setState(prev => ({ ...prev, loading, error }))
  }, [])

  const setActiveStep = useCallback((step) => {
    setState(prev => ({ ...prev, activeStep: step }))
  }, [])

  // ── 업로드 ──
  const setUploadedFiles = useCallback((face, files) => {
    setState(prev => ({
      ...prev,
      uploadedFiles: { ...prev.uploadedFiles, [face]: files },
    }))
  }, [])

  // ── 전처리 결과 (함수형 업데이트 지원: 배열 누적) ──
  const setPreprocessResult = useCallback((face, resultOrFn) => {
    setState(prev => {
      const current = prev.preprocessed[face]
      const next = typeof resultOrFn === 'function' ? resultOrFn(current) : resultOrFn
      return {
        ...prev,
        preprocessed: { ...prev.preprocessed, [face]: next },
      }
    })
  }, [])

  // ── 파노라마 결과 ──
  const setPanoramaResult = useCallback((face, result) => {
    setState(prev => ({
      ...prev,
      panoramas: { ...prev.panoramas, [face]: result },
    }))
  }, [])

  // ── 전개도 결과 ──
  const setCubenetResult = useCallback((result) => {
    setState(prev => ({ ...prev, cubenet: result }))
  }, [])

  // ── 초기화 ──
  const reset = useCallback(() => {
    setState(initialState)
  }, [])

  return {
    state,
    setLoading,
    setActiveStep,
    setUploadedFiles,
    setPreprocessResult,
    setPanoramaResult,
    setCubenetResult,
    reset,
  }
}
