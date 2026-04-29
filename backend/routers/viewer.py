"""
3D 모델 조립 API 라우터
GET /api/viewer/faces - 면별 텍스처 이미지 URL 반환
POST /api/viewer/export-obj - OBJ 형식 3D 모델 내보내기
"""
import uuid
import cv2
import numpy as np
from pathlib import Path
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

PREPROCESS_DIR = Path("outputs/preprocess")
PANORAMA_DIR = Path("outputs/panorama")
OUTPUT_DIR = Path("outputs/viewer")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FACES = ["front", "back", "left", "right", "top"]


def find_face_texture(face: str) -> Path | None:
    """면별 최적 텍스처 이미지 경로 반환 (전처리 결과 우선)"""
    # 1. warped (perspective 보정 직사각형) — 최우선
    for fp in sorted(PREPROCESS_DIR.glob(f"{face}_*_warped.png"), reverse=True):
        return fp
    # 2. 배경 분리 (PNG, 투명)
    for fp in sorted(PREPROCESS_DIR.glob(f"{face}_*_separated.png"), reverse=True):
        return fp
    # 3. 파노라마 (fallback)
    for fp in sorted(PANORAMA_DIR.glob(f"{face}_*_panorama*.jpg"), reverse=True):
        return fp
    # 4. 원본
    upload_dir = Path("uploads")
    for fp in sorted(upload_dir.glob(f"{face}_*"), reverse=True):
        return fp
    return None


@router.get("/faces")
async def get_face_textures():
    """
    면별 텍스처 이미지 URL 반환
    three.js에서 각 면에 텍스처를 입힐 때 사용
    """
    face_urls = {}
    sources = {}
    for face in FACES:
        fp = find_face_texture(face)
        if fp is not None:
            # 상대 경로로 변환
            parts = fp.parts
            try:
                idx = parts.index("outputs")
                rel = "/".join(parts[idx:])
                face_urls[face] = f"/{rel}"
            except ValueError:
                try:
                    idx = parts.index("uploads")
                    rel = "/".join(parts[idx:])
                    face_urls[face] = f"/{rel}"
                except ValueError:
                    continue

            # 소스 판별
            name = fp.name
            if "panorama" in name:
                sources[face] = "panorama"
            elif "separated" in name:
                sources[face] = "separated"
            elif "cropped" in name:
                sources[face] = "cropped"
            elif "corrected" in name:
                sources[face] = "corrected"
            else:
                sources[face] = "original"

    return JSONResponse({
        "faces": face_urls,
        "sources": sources,
        "available_count": len(face_urls),
    })


@router.post("/export-obj")
async def export_obj(
    face_size: int = Form(512),
):
    """
    OBJ + MTL 형식으로 3D 큐브 모델 내보내기
    각 면에 텍스처를 매핑한 상태
    """
    export_id = str(uuid.uuid4())[:8]

    # 면별 텍스처 준비 (정사각형 정규화)
    texture_files = {}
    for face in FACES:
        fp = find_face_texture(face)
        if fp is not None:
            img = cv2.imread(str(fp), cv2.IMREAD_UNCHANGED)
            if img is not None:
                resized = cv2.resize(img, (face_size, face_size))
                out = OUTPUT_DIR / f"{export_id}_{face}.png"
                cv2.imwrite(str(out), resized)
                texture_files[face] = out.name

    if not texture_files:
        raise HTTPException(400, "텍스처 이미지가 없습니다")

    # OBJ 파일 생성 (단위 큐브)
    obj_content = _generate_obj(texture_files, export_id)
    obj_path = OUTPUT_DIR / f"{export_id}_model.obj"
    obj_path.write_text(obj_content)

    # MTL 파일 생성
    mtl_content = _generate_mtl(texture_files, export_id)
    mtl_path = OUTPUT_DIR / f"{export_id}_model.mtl"
    mtl_path.write_text(mtl_content)

    return JSONResponse({
        "export_id": export_id,
        "obj_url": f"/outputs/viewer/{obj_path.name}",
        "mtl_url": f"/outputs/viewer/{mtl_path.name}",
        "textures": {f: f"/outputs/viewer/{fn}" for f, fn in texture_files.items()},
    })


def _generate_obj(textures: dict, export_id: str) -> str:
    """OBJ 형식 큐브 생성"""
    lines = [
        f"# 3D Modeling Pipeline - Export {export_id}",
        f"mtllib {export_id}_model.mtl",
        "",
        "# Vertices",
        "v -0.5 -0.5  0.5",  # 1: 전면 좌하
        "v  0.5 -0.5  0.5",  # 2: 전면 우하
        "v  0.5  0.5  0.5",  # 3: 전면 우상
        "v -0.5  0.5  0.5",  # 4: 전면 좌상
        "v -0.5 -0.5 -0.5",  # 5: 후면 좌하
        "v  0.5 -0.5 -0.5",  # 6: 후면 우하
        "v  0.5  0.5 -0.5",  # 7: 후면 우상
        "v -0.5  0.5 -0.5",  # 8: 후면 좌상
        "",
        "# Texture coordinates",
        "vt 0.0 0.0",  # 1
        "vt 1.0 0.0",  # 2
        "vt 1.0 1.0",  # 3
        "vt 0.0 1.0",  # 4
        "",
        "# Normals",
        "vn  0.0  0.0  1.0",  # front
        "vn  0.0  0.0 -1.0",  # back
        "vn -1.0  0.0  0.0",  # left
        "vn  1.0  0.0  0.0",  # right
        "vn  0.0  1.0  0.0",  # top
        "vn  0.0 -1.0  0.0",  # bottom
        "",
    ]

    # 면별 face 정의
    face_defs = {
        "front":  ("mat_front",  "f 1/1/1 2/2/1 3/3/1 4/4/1"),
        "back":   ("mat_back",   "f 6/1/2 5/2/2 8/3/2 7/4/2"),
        "left":   ("mat_left",   "f 5/1/3 1/2/3 4/3/3 8/4/3"),
        "right":  ("mat_right",  "f 2/1/4 6/2/4 7/3/4 3/4/4"),
        "top":    ("mat_top",    "f 4/1/5 3/2/5 7/3/5 8/4/5"),
    }

    for face_name, (mat_name, face_line) in face_defs.items():
        if face_name in textures:
            lines.append(f"usemtl {mat_name}")
        else:
            lines.append("usemtl mat_default")
        lines.append(face_line)
        lines.append("")

    return "\n".join(lines)


def _generate_mtl(textures: dict, export_id: str) -> str:
    """MTL 재질 파일 생성"""
    lines = [f"# Material file for {export_id}", ""]

    for face_name, filename in textures.items():
        lines.extend([
            f"newmtl mat_{face_name}",
            "Ka 1.0 1.0 1.0",
            "Kd 1.0 1.0 1.0",
            "Ks 0.0 0.0 0.0",
            "Ns 10.0",
            "illum 1",
            f"map_Kd {filename}",
            "",
        ])

    # 기본 재질 (텍스처 없는 면)
    lines.extend([
        "newmtl mat_default",
        "Ka 0.5 0.5 0.5",
        "Kd 0.7 0.7 0.7",
        "Ks 0.0 0.0 0.0",
        "",
    ])

    return "\n".join(lines)
