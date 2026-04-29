/**
 * 모듈 4+5: Visual Hull 3D 복원 + 면별 텍스처 매핑
 */
import { useState, useRef, useCallback, useEffect } from 'react'
import { Download, RefreshCw, AlertTriangle, Box } from 'lucide-react'
import { reconstructAPI } from '../../utils/api'
import { FACE_LABELS } from '../../utils/constants'
import StatusBadge from '../../components/StatusBadge'

export default function ViewerStep() {
  const [reconstructing, setReconstructing] = useState(false)
  const [modelData, setModelData] = useState(null)
  const [error, setError] = useState(null)
  const [resolution, setResolution] = useState(128)
  const [autoRotate, setAutoRotate] = useState(true)
  const [wireframe, setWireframe] = useState(false)
  const [showTexture, setShowTexture] = useState(true)

  const handleReconstruct = async () => {
    setReconstructing(true)
    setError(null)
    try {
      const res = await reconstructAPI.build(resolution)
      const meshRes = await reconstructAPI.getMesh(res.data.model_id)
      setModelData({ ...res.data, geometry: meshRes.data })
    } catch (err) {
      setError(err.response?.data?.detail || '3D 복원 실패')
    } finally {
      setReconstructing(false)
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-medium text-slate-200 mb-1">3D 모델 복원</h2>
          <p className="text-sm text-slate-400">Visual Hull 외곽선 기반 + 면별 텍스처 매핑</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={resolution} onChange={e => setResolution(Number(e.target.value))}
            className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-slate-300">
            <option value={64}>64³</option>
            <option value={128}>128³</option>
            <option value={256}>256³</option>
          </select>
          <button onClick={handleReconstruct} disabled={reconstructing}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg text-sm font-medium transition-colors">
            {reconstructing ? <RefreshCw size={14} className="animate-spin" /> : <Box size={14} />}
            3D 복원
          </button>
          {modelData?.obj_url && (
            <button onClick={() => { const a = document.createElement('a'); a.href = modelData.obj_url; a.download = 'model.obj'; a.click() }}
              className="flex items-center gap-1 px-3 py-2 text-xs bg-slate-700 hover:bg-slate-600 rounded-lg">
              <Download size={12} /> OBJ
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 mb-4 p-3 bg-red-900/20 border border-red-700/30 rounded-lg">
          <AlertTriangle size={16} className="text-red-400 mt-0.5" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}

      {modelData && (
        <>
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <StatusBadge status="success" label={`${modelData.faces_used?.length || 0}방향`} />
            {modelData.shape_type && (
              <span className={`text-xs px-2 py-0.5 rounded ${modelData.shape_type === 'rectangle' ? 'bg-blue-900/40 text-blue-300' : 'bg-purple-900/40 text-purple-300'}`}>
                {modelData.shape_type === 'rectangle' ? '직사각형' : '곡면'}
              </span>
            )}
            <span className="text-xs text-slate-500">
              정점 {modelData.stats?.vertex_count?.toLocaleString()} · 면 {modelData.stats?.face_count?.toLocaleString()}
            </span>
          </div>
          <div className="flex items-center gap-4 mb-4 text-sm">
            <label className="flex items-center gap-2 text-slate-400 cursor-pointer">
              <input type="checkbox" checked={autoRotate} onChange={e => setAutoRotate(e.target.checked)} className="accent-blue-500" />
              자동 회전
            </label>
            <label className="flex items-center gap-2 text-slate-400 cursor-pointer">
              <input type="checkbox" checked={wireframe} onChange={e => setWireframe(e.target.checked)} className="accent-blue-500" />
              와이어프레임
            </label>
            <label className="flex items-center gap-2 text-slate-400 cursor-pointer">
              <input type="checkbox" checked={showTexture} onChange={e => setShowTexture(e.target.checked)} className="accent-blue-500" />
              텍스처
            </label>
          </div>
        </>
      )}

      {!modelData && !reconstructing && (
        <div className="text-center py-20 text-slate-500">
          <Box size={40} className="mx-auto mb-3 text-slate-600" />
          <p className="text-sm">전처리 완료 후 "3D 복원" 버튼을 눌러주세요</p>
        </div>
      )}

      {reconstructing && (
        <div className="text-center py-20">
          <RefreshCw size={32} className="mx-auto mb-3 text-blue-400 animate-spin" />
          <p className="text-sm text-slate-400">Visual Hull 계산 중...</p>
        </div>
      )}

      {modelData?.geometry && (
        <div className="bg-slate-900/80 rounded-xl border border-slate-700/50 overflow-hidden" style={{ height: '560px' }}>
          <MeshViewer
            geometry={modelData.geometry}
            textureUrls={modelData.texture_urls || {}}
            autoRotate={autoRotate}
            wireframe={wireframe}
            showTexture={showTexture}
          />
        </div>
      )}
    </div>
  )
}

function MeshViewer({ geometry, textureUrls, autoRotate, wireframe, showTexture }) {
  const containerRef = useRef(null)
  const stateRef = useRef({
    scene: null, camera: null, renderer: null,
    group: null, meshWire: null, animId: null,
    isDragging: false, prevMouse: { x: 0, y: 0 },
    rotX: -0.4, rotY: 0.6,
  })

  const initScene = useCallback(async () => {
    const THREE = await import('three')
    const container = containerRef.current
    if (!container || !geometry) return
    const s = stateRef.current

    if (s.renderer) { s.renderer.dispose(); container.innerHTML = '' }

    const w = container.clientWidth, h = container.clientHeight
    s.scene = new THREE.Scene()
    s.camera = new THREE.PerspectiveCamera(50, w / h, 0.01, 100)
    s.camera.position.set(0, 0.3, 3)
    s.renderer = new THREE.WebGLRenderer({ antialias: true })
    s.renderer.setSize(w, h)
    s.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    s.renderer.setClearColor(0x0d1520, 1)
    container.appendChild(s.renderer.domElement)

    s.scene.add(new THREE.AmbientLight(0xffffff, 0.6))
    const d1 = new THREE.DirectionalLight(0xffffff, 0.7)
    d1.position.set(3, 4, 5)
    s.scene.add(d1)
    s.scene.add(new THREE.DirectionalLight(0x6688aa, 0.3).position.set(-3, -2, -3) || new THREE.DirectionalLight(0x6688aa, 0.3))

    // Geometry
    const bufGeom = new THREE.BufferGeometry()
    bufGeom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(geometry.vertices), 3))
    bufGeom.setIndex(new THREE.BufferAttribute(new Uint32Array(geometry.faces), 1))
    bufGeom.computeVertexNormals()

    if (geometry.uvs && geometry.uvs.length > 0) {
      bufGeom.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(geometry.uvs), 2))
    }

    s.group = new THREE.Group()

    if (showTexture && Object.keys(textureUrls).length > 0) {
      // ── 면별 텍스처: face_texture_ids로 geometry를 6개 그룹으로 분리 ──
      const faceIds = geometry.face_texture_ids || []
      const faceNames = ['front', 'back', 'left', 'right', 'top', 'bottom']
      const loader = new THREE.TextureLoader()

      // 삼각형별 face_id 결정 (3 정점의 다수결)
      const numTriangles = geometry.faces.length / 3
      const triFaceIds = new Array(numTriangles)
      for (let t = 0; t < numTriangles; t++) {
        const i0 = geometry.faces[t * 3]
        const i1 = geometry.faces[t * 3 + 1]
        const i2 = geometry.faces[t * 3 + 2]
        const ids = [faceIds[i0] || 0, faceIds[i1] || 0, faceIds[i2] || 0]
        // 다수결
        const counts = {}
        ids.forEach(id => { counts[id] = (counts[id] || 0) + 1 })
        triFaceIds[t] = parseInt(Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0])
      }

      // 면별로 삼각형 인덱스 분리
      for (let fid = 0; fid < 6; fid++) {
        const faceName = faceNames[fid]
        const triIndices = []
        for (let t = 0; t < numTriangles; t++) {
          if (triFaceIds[t] === fid) {
            triIndices.push(
              geometry.faces[t * 3],
              geometry.faces[t * 3 + 1],
              geometry.faces[t * 3 + 2]
            )
          }
        }
        if (triIndices.length === 0) continue

        const subGeom = bufGeom.clone()
        subGeom.setIndex(new THREE.BufferAttribute(new Uint32Array(triIndices), 1))

        let mat
        const texUrl = textureUrls[faceName]
        if (texUrl) {
          try {
            const tex = await new Promise((res, rej) => loader.load(texUrl, res, undefined, rej))
            tex.colorSpace = THREE.SRGBColorSpace
            mat = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.4, metalness: 0.05, side: THREE.DoubleSide })
          } catch {
            mat = new THREE.MeshStandardMaterial({ color: 0x888888, roughness: 0.5, side: THREE.DoubleSide })
          }
        } else {
          const colors = [0x4488cc, 0x8855cc, 0x22aa88, 0x22cc66, 0xddaa22, 0xdd8822]
          mat = new THREE.MeshStandardMaterial({ color: colors[fid], roughness: 0.5, side: THREE.DoubleSide })
        }

        s.group.add(new THREE.Mesh(subGeom, mat))
      }
    } else {
      // 텍스처 OFF: 면별 색상
      if (geometry.face_texture_ids) {
        const faceColors = [[0.3,0.5,0.9],[0.5,0.3,0.8],[0.2,0.7,0.6],[0.2,0.8,0.4],[0.9,0.7,0.2],[0.9,0.5,0.1]]
        const colors = new Float32Array(geometry.vertices.length)
        for (let i = 0; i < geometry.face_texture_ids.length; i++) {
          const c = faceColors[geometry.face_texture_ids[i]] || [0.5,0.5,0.5]
          colors[i*3] = c[0]; colors[i*3+1] = c[1]; colors[i*3+2] = c[2]
        }
        bufGeom.setAttribute('color', new THREE.BufferAttribute(colors, 3))
        s.group.add(new THREE.Mesh(bufGeom, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.5, side: THREE.DoubleSide })))
      } else {
        s.group.add(new THREE.Mesh(bufGeom, new THREE.MeshStandardMaterial({ color: 0x4488cc, roughness: 0.5, side: THREE.DoubleSide })))
      }
    }

    s.scene.add(s.group)

    // Wireframe
    s.meshWire = new THREE.LineSegments(
      new THREE.WireframeGeometry(bufGeom),
      new THREE.LineBasicMaterial({ color: 0x88aacc, opacity: 0.15, transparent: true })
    )
    s.group.add(s.meshWire)

    // Grid + axes
    const grid = new THREE.GridHelper(4, 10, 0x1e293b, 0x1e293b)
    grid.position.y = -0.7
    s.scene.add(grid)
  }, [geometry, textureUrls, showTexture])

  useEffect(() => {
    const s = stateRef.current
    if (!s.renderer) return
    const animate = () => {
      s.animId = requestAnimationFrame(animate)
      if (autoRotate && !s.isDragging) s.rotY += 0.005
      if (s.group) { s.group.rotation.x = s.rotX; s.group.rotation.y = s.rotY }
      if (s.meshWire) s.meshWire.visible = wireframe
      s.renderer.render(s.scene, s.camera)
    }
    animate()
    return () => { if (s.animId) cancelAnimationFrame(s.animId) }
  }, [autoRotate, wireframe])

  useEffect(() => {
    initScene()
    return () => { const s = stateRef.current; if (s.animId) cancelAnimationFrame(s.animId); if (s.renderer) s.renderer.dispose() }
  }, [initScene])

  useEffect(() => {
    const c = containerRef.current
    if (!c) return
    const s = stateRef.current
    const onDown = e => { s.isDragging = true; s.prevMouse = { x: e.clientX, y: e.clientY } }
    const onMove = e => { if (!s.isDragging) return; s.rotY += (e.clientX - s.prevMouse.x) * 0.008; s.rotX += (e.clientY - s.prevMouse.y) * 0.008; s.prevMouse = { x: e.clientX, y: e.clientY } }
    const onUp = () => s.isDragging = false
    const onWheel = e => { e.preventDefault(); if (s.camera) s.camera.position.z = Math.max(1, Math.min(10, s.camera.position.z + e.deltaY * 0.003)) }
    c.addEventListener('mousedown', onDown); c.addEventListener('mousemove', onMove)
    c.addEventListener('mouseup', onUp); c.addEventListener('mouseleave', onUp)
    c.addEventListener('wheel', onWheel, { passive: false })
    return () => { c.removeEventListener('mousedown', onDown); c.removeEventListener('mousemove', onMove); c.removeEventListener('mouseup', onUp); c.removeEventListener('mouseleave', onUp); c.removeEventListener('wheel', onWheel) }
  }, [])

  useEffect(() => {
    const c = containerRef.current
    if (!c) return
    const s = stateRef.current
    const obs = new ResizeObserver(() => {
      if (!s.camera || !s.renderer) return
      s.camera.aspect = c.clientWidth / c.clientHeight
      s.camera.updateProjectionMatrix()
      s.renderer.setSize(c.clientWidth, c.clientHeight)
    })
    obs.observe(c)
    return () => obs.disconnect()
  }, [])

  return <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />
}
