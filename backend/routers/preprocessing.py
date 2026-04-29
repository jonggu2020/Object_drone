"""
전처리 API 라우터
POST /api/preprocess/upload - 이미지 업로드 및 전처리 실행
"""
import uuid
import cv2
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from modules.preprocessing import process_image

router = APIRouter()

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs/preprocess")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_and_preprocess(
    file: UploadFile = File(...),
    ksize: int = 5,
    face: str = "front",
    use_ai: bool = True,
):
    """
    이미지 업로드 → 메디안 스무딩 → 엣지 검출 → 배경 분리
    face: 어느 면인지 ("front", "back", "left", "right", "top")
    use_ai: True이면 rembg AI 모델 우선 사용
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "이미지 파일만 업로드 가능합니다")

    # 파일 저장
    file_id = str(uuid.uuid4())[:8]
    ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    save_path = UPLOAD_DIR / f"{face}_{file_id}{ext}"

    content = await file.read()
    save_path.write_bytes(content)

    # OpenCV로 로드
    import numpy as np
    nparr = np.frombuffer(content, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "이미지 디코딩 실패")

    # 전처리 실행
    result = process_image(image, ksize, use_ai)

    # 결과 이미지 저장
    outputs = {}

    # JPG: 시각화용
    for key in ["smoothed", "edges", "lines_vis", "quad_vis"]:
        img = result.get(key)
        if img is not None:
            out_path = OUTPUT_DIR / f"{face}_{file_id}_{key}.jpg"
            cv2.imwrite(str(out_path), img)
            outputs[key] = f"/outputs/preprocess/{out_path.name}"

    # PNG: warped (핵심 — 전개도/3D에 사용)
    warped = result.get("warped")
    if warped is not None:
        out_path = OUTPUT_DIR / f"{face}_{file_id}_warped.png"
        cv2.imwrite(str(out_path), warped)
        outputs["warped"] = f"/outputs/preprocess/{out_path.name}"

    # PNG: separated (투명 배경)
    separated = result.get("separated")
    if separated is not None:
        out_path = OUTPUT_DIR / f"{face}_{file_id}_separated.png"
        cv2.imwrite(str(out_path), separated)
        outputs["separated"] = f"/outputs/preprocess/{out_path.name}"

    # PNG: mask
    if result["mask"] is not None:
        mask_path = OUTPUT_DIR / f"{face}_{file_id}_mask.png"
        cv2.imwrite(str(mask_path), result["mask"])
        outputs["mask"] = f"/outputs/preprocess/{mask_path.name}"

    return JSONResponse({
        "file_id": file_id,
        "face": face,
        "original": f"/uploads/{save_path.name}",
        "outputs": outputs,
        "contour_found": result["contour_found"],
        "quad_found": result.get("quad_found", False),
        "method": result.get("method", "opencv"),
        "rembg_available": result.get("rembg_available", False),
        "line_count": result.get("line_count", 0),
    })


@router.get("/results/{file_id}")
async def get_preprocess_results(file_id: str):
    """특정 파일의 전처리 결과 조회"""
    results = {}
    for path in OUTPUT_DIR.glob(f"*{file_id}*"):
        key = path.stem.split("_")[-1]
        results[key] = f"/outputs/preprocess/{path.name}"

    if not results:
        raise HTTPException(404, "결과를 찾을 수 없습니다")

    return {"file_id": file_id, "outputs": results}
