"""
Visual Hull 3D 복원 API 라우터 (v3 — 텍스처 지원)
"""
import uuid
import cv2
import json
import numpy as np
from pathlib import Path
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse
import traceback

from modules.visual_hull import reconstruct_3d, export_obj

router = APIRouter()

PREPROCESS_DIR = Path("outputs/preprocess")
OUTPUT_DIR = Path("outputs/reconstruct")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FACES = ["front", "back", "left", "right", "top"]


def find_mask(face: str) -> np.ndarray | None:
    for fp in sorted(PREPROCESS_DIR.glob(f"{face}_*_mask.png"), reverse=True):
        img = cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            return img
    for fp in sorted(PREPROCESS_DIR.glob(f"{face}_*_separated.png"), reverse=True):
        img = cv2.imread(str(fp), cv2.IMREAD_UNCHANGED)
        if img is not None and len(img.shape) == 3 and img.shape[2] == 4:
            return img[:, :, 3]
    return None


def find_texture_url(face: str) -> str | None:
    """면별 텍스처 이미지 URL 탐색 (warped > separated > original)"""
    for fp in sorted(PREPROCESS_DIR.glob(f"{face}_*_warped.png"), reverse=True):
        parts = fp.parts
        idx = next((i for i, p in enumerate(parts) if p == "outputs"), None)
        if idx is not None:
            return "/" + "/".join(parts[idx:])
    for fp in sorted(PREPROCESS_DIR.glob(f"{face}_*_separated.png"), reverse=True):
        parts = fp.parts
        idx = next((i for i, p in enumerate(parts) if p == "outputs"), None)
        if idx is not None:
            return "/" + "/".join(parts[idx:])
    upload_dir = Path("uploads")
    for fp in sorted(upload_dir.glob(f"{face}_*"), reverse=True):
        return f"/uploads/{fp.name}"
    return None


@router.post("/build")
async def build_3d_model(
    resolution: int = Form(128),
    smooth: bool = Form(True),
):
    """전처리 마스크 → 외곽선 기반 Visual Hull → 텍스처 매핑 메시"""

    # 마스크 수집
    silhouettes = {}
    found_faces = []
    for face in FACES:
        mask = find_mask(face)
        if mask is not None:
            silhouettes[face] = mask
            found_faces.append(face)
            print(f"[reconstruct] {face} 마스크 OK: {mask.shape}")

    if len(silhouettes) < 2:
        raise HTTPException(400, f"마스크 부족 ({len(silhouettes)}개: {found_faces})")
    if "front" not in silhouettes:
        raise HTTPException(400, "전면(front) 마스크 필요")

    # 3D 복원
    try:
        result = reconstruct_3d(silhouettes, resolution=resolution, smooth=smooth)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"복원 실패: {str(e)}")

    if result.get("error"):
        raise HTTPException(500, result["error"])

    mesh = result.get("mesh")
    if mesh is None or len(mesh.get("vertices", [])) == 0:
        raise HTTPException(500, "메시 생성 실패")

    verts = mesh["vertices"]
    faces_arr = mesh["faces"]

    # 저장
    model_id = str(uuid.uuid4())[:8]
    export_obj(mesh, str(OUTPUT_DIR / f"model_{model_id}.obj"))

    # three.js용 JSON (정점 + 면 + UV + face_texture_ids)
    geometry_json = {
        "vertices": verts.flatten().tolist(),
        "faces": faces_arr.flatten().tolist(),
        "uvs": mesh["uvs"].flatten().tolist() if "uvs" in mesh else [],
        "vertex_count": len(verts),
        "face_count": len(faces_arr),
    }

    # 정점별 텍스처 면 ID
    fti = mesh.get("face_texture_ids")
    if fti is not None:
        geometry_json["face_texture_ids"] = fti.tolist()

    json_path = OUTPUT_DIR / f"model_{model_id}.json"
    json_path.write_text(json.dumps(geometry_json))

    # 텍스처 URL 수집 (6면: bottom = top 이미지 재활용)
    texture_urls = {}
    for face in FACES:
        url = find_texture_url(face)
        if url:
            texture_urls[face] = url
    # 밑면에 상단 이미지 적용
    if "top" in texture_urls and "bottom" not in texture_urls:
        texture_urls["bottom"] = texture_urls["top"]

    return JSONResponse({
        "model_id": model_id,
        "obj_url": f"/outputs/reconstruct/model_{model_id}.obj",
        "mesh_url": f"/outputs/reconstruct/model_{model_id}.json",
        "texture_urls": texture_urls,
        "shape_type": result.get("shape_type", "unknown"),
        "shape_info": result.get("shape_info", {}),
        "stats": {
            "resolution": result.get("resolution", resolution),
            "voxel_count": result.get("voxel_count", 0),
            "filled_ratio": result.get("fill_ratio", 0),
            "vertex_count": len(verts),
            "face_count": len(faces_arr),
            "proportions": result.get("proportions", {}),
        },
        "faces_used": result.get("directions_used", found_faces),
    })


@router.get("/mesh/{model_id}")
async def get_mesh_data(model_id: str):
    json_path = OUTPUT_DIR / f"model_{model_id}.json"
    if not json_path.exists():
        raise HTTPException(404, "모델 없음")
    return JSONResponse(json.loads(json_path.read_text()))
