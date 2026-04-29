"""
전개도 구성 API 라우터 (v3)

변경점:
- 세션(file_id) 기반으로 현재 전처리 결과만 사용
- 전면 기준 공유 변 정규화 (정사각형 강제 없음)
- 실제 크기/비율 유지
"""
import uuid
import cv2
import numpy as np
from pathlib import Path
from fastapi import APIRouter, Form, Body, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

from modules.cubenet import create_cube_net, draw_fold_guides

router = APIRouter()

PREPROCESS_DIR = Path("outputs/preprocess")
PANORAMA_DIR = Path("outputs/panorama")
OUTPUT_DIR = Path("outputs/cubenet")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FACES = ["front", "back", "left", "right", "top"]


def find_best_image(face: str) -> tuple[np.ndarray | None, str]:
    """
    면별 최적 이미지 탐색
    우선순위: warped(정면보정) > separated > 원본
    """
    # 1. warped (perspective 보정 — 깔끔한 직사각형)
    for fp in sorted(PREPROCESS_DIR.glob(f"{face}_*_warped.png"), reverse=True):
        img = cv2.imread(str(fp), cv2.IMREAD_UNCHANGED)
        if img is not None:
            return img, "warped"

    # 2. separated (배경 제거)
    for fp in sorted(PREPROCESS_DIR.glob(f"{face}_*_separated.png"), reverse=True):
        img = cv2.imread(str(fp), cv2.IMREAD_UNCHANGED)
        if img is not None:
            return img, "separated"

    # 3. 원본
    upload_dir = Path("uploads")
    for fp in sorted(upload_dir.glob(f"{face}_*"), reverse=True):
        img = cv2.imread(str(fp))
        if img is not None:
            return img, "original"

    return None, "none"


@router.post("/build-auto")
async def build_cube_net_auto(
    face_size: Optional[int] = Form(None),
    show_guides: bool = Form(True),
):
    """
    전처리 결과를 자동으로 찾아서 전개도 구성
    face_size=None이면 실제 크기 유지 (적응형)
    """
    face_images = {}
    sources = {}
    for face in FACES:
        img, source = find_best_image(face)
        if img is not None:
            face_images[face] = img
            sources[face] = source

    if not face_images:
        raise HTTPException(400, "사용 가능한 이미지가 없습니다. 먼저 이미지를 업로드하고 전처리를 실행하세요.")

    if "front" not in face_images:
        raise HTTPException(400, "전면(front) 이미지가 필요합니다. 전면을 기준으로 전개도가 구성됩니다.")

    # 전개도 생성 (적응형)
    result = create_cube_net(face_images)

    net_image = result["net_image"]
    if show_guides:
        net_image = draw_fold_guides(net_image, result["face_rects"])

    net_id = str(uuid.uuid4())[:8]
    out_path = OUTPUT_DIR / f"cubenet_{net_id}.png"
    cv2.imwrite(str(out_path), net_image)

    return JSONResponse({
        "net_id": net_id,
        "net_url": f"/outputs/cubenet/{out_path.name}",
        "faces_used": result["faces_used"],
        "missing_faces": result["missing_faces"],
        "front_size": result["front_size"],
        "face_rects": {k: list(v) for k, v in result["face_rects"].items()},
        "sources": sources,
    })
