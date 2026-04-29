"""
3D 모델링 파이프라인 - FastAPI 메인 서버
각 모듈은 독립적인 라우터로 분리되어 있음
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from routers import preprocessing, panorama, cubenet, viewer, reconstruct

app = FastAPI(
    title="3D Modeling Pipeline",
    description="드론 활용 사물 3D 모델링 백엔드 API",
    version="0.1.0",
)

# CORS 설정 (외부 접속 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 업로드/출력 디렉토리 생성
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

# 정적 파일 서빙 (처리 결과 이미지 접근용)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# ── 모듈별 라우터 등록 ──
app.include_router(preprocessing.router, prefix="/api/preprocess", tags=["전처리"])
app.include_router(panorama.router, prefix="/api/panorama", tags=["파노라마"])
app.include_router(cubenet.router, prefix="/api/cubenet", tags=["전개도"])
app.include_router(viewer.router, prefix="/api/viewer", tags=["3D 뷰어"])
app.include_router(reconstruct.router, prefix="/api/reconstruct", tags=["3D 복원"])


# ── 프론트엔드 빌드 서빙 (포트 8000 통합 배포용) ──
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """프론트엔드 SPA fallback — API/uploads/outputs 외 모든 경로"""
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


@app.get("/api/health")
def health_check():
    return {"status": "ok", "modules": ["preprocessing", "panorama", "cubenet"]}


@app.post("/api/reset")
def reset_outputs():
    """이전 처리 결과 전체 삭제 (새 세션 시작)"""
    import shutil
    cleared = []
    for d in ["uploads", "outputs/preprocess", "outputs/panorama", "outputs/cubenet", "outputs/viewer"]:
        path = os.path.join(os.getcwd(), d)
        if os.path.exists(path):
            count = len(os.listdir(path))
            shutil.rmtree(path)
            os.makedirs(path, exist_ok=True)
            cleared.append(f"{d}: {count}개 삭제")
    return {"status": "reset", "cleared": cleared}
