"""
파노라마 합성 API 라우터
POST /api/panorama/stitch - 같은 면의 여러 이미지를 파노라마 합성
"""
import uuid
import cv2
import numpy as np
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

from modules.panorama import stitch_images, normalize_sizes

router = APIRouter()

OUTPUT_DIR = Path("outputs/panorama")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/stitch")
async def stitch_face_images(
    files: list[UploadFile] = File(...),
    face: str = Form("front"),
    method: str = Form("orb"),
    target_height: Optional[int] = Form(800),
):
    """
    같은 면에서 촬영한 여러 장의 이미지를 파노라마 합성
    files: 이미지 파일 리스트
    face: 면 이름 ("front", "back", "left", "right", "top")
    method: 특징점 검출 방식 ("orb" 또는 "sift")
    """
    if len(files) < 1:
        raise HTTPException(400, "최소 1장 이상의 이미지가 필요합니다")

    # 이미지 로드
    images = []
    for f in files:
        content = await f.read()
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(400, f"이미지 디코딩 실패: {f.filename}")
        images.append(img)

    # 크기 정규화
    if target_height:
        images = normalize_sizes(images, target_height)

    # 파노라마 합성
    result = stitch_images(images, method=method)

    if not result["success"] or result["panorama"] is None:
        raise HTTPException(500, "파노라마 합성 실패")

    # 결과 저장
    stitch_id = str(uuid.uuid4())[:8]
    out_path = OUTPUT_DIR / f"{face}_{stitch_id}_panorama.jpg"
    cv2.imwrite(str(out_path), result["panorama"])

    return JSONResponse({
        "stitch_id": stitch_id,
        "face": face,
        "input_count": len(images),
        "match_counts": result["match_counts"],
        "panorama_url": f"/outputs/panorama/{out_path.name}",
    })


@router.post("/stitch-preprocessed")
async def stitch_preprocessed_images(
    face: str = Form("front"),
    method: str = Form("orb"),
    target_height: Optional[int] = Form(800),
):
    """
    전처리 완료된 보정 이미지(corrected)를 사용하여 파노라마 합성
    서버에 저장된 outputs/preprocess/{face}_*_corrected.jpg 파일들을 자동 탐색
    """
    preprocess_dir = Path("outputs/preprocess")
    corrected_files = sorted(preprocess_dir.glob(f"{face}_*_corrected.jpg"))

    if len(corrected_files) < 2:
        raise HTTPException(400, f"전처리된 보정 이미지가 2장 이상 필요합니다 (현재 {len(corrected_files)}장)")

    images = []
    for fp in corrected_files:
        img = cv2.imread(str(fp))
        if img is not None:
            images.append(img)

    if len(images) < 2:
        raise HTTPException(400, "유효한 보정 이미지가 2장 미만입니다")

    if target_height:
        images = normalize_sizes(images, target_height)

    result = stitch_images(images, method=method)

    if not result["success"] or result["panorama"] is None:
        raise HTTPException(500, "파노라마 합성 실패")

    stitch_id = str(uuid.uuid4())[:8]
    out_path = OUTPUT_DIR / f"{face}_{stitch_id}_panorama_corrected.jpg"
    cv2.imwrite(str(out_path), result["panorama"])

    return JSONResponse({
        "stitch_id": stitch_id,
        "face": face,
        "input_count": len(images),
        "match_counts": result["match_counts"],
        "panorama_url": f"/outputs/panorama/{out_path.name}",
        "source": "preprocessed_corrected",
    })
