"""
모듈 1: 이미지 전처리 (v4 - Perspective 보정)

파이프라인:
  1. 메디안 스무딩
  2. 배경 분리 (AI 우선, OpenCV fallback)
  3. 사물 면의 4꼭짓점 검출 (컨투어 → 근사 사각형)
  4. Perspective warp → 깔끔한 직사각형 면 이미지 출력
  5. 엣지/직선 검출 (시각화용)

핵심: 촬영된 사물의 면을 정면에서 본 것처럼 왜곡 제거
"""
import cv2
import numpy as np
import math

# rembg
try:
    from rembg import remove as rembg_remove, new_session
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False

# GPU 자동 감지
GPU_AVAILABLE = False
try:
    import onnxruntime as ort
    providers = ort.get_available_providers()
    GPU_AVAILABLE = "CUDAExecutionProvider" in providers
    print(f"[rembg] ONNX providers: {providers}")
    if GPU_AVAILABLE:
        print("[rembg] GPU 모드: ON (CUDA)")
    else:
        print("[rembg] GPU 모드: OFF (CPU)")
        print("[rembg] GPU 전환: pip uninstall onnxruntime -y && pip install onnxruntime-gpu")
        print("[rembg] CUDA Toolkit + cuDNN 설치 필요 (https://developer.nvidia.com/cuda-downloads)")
except ImportError:
    pass

_rembg_session = None

def get_rembg_session(model_name: str = "u2net"):
    global _rembg_session
    if _rembg_session is None and REMBG_AVAILABLE:
        if GPU_AVAILABLE:
            # GPU 세션 생성
            _rembg_session = new_session(model_name, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
            print(f"[rembg] GPU 세션 생성: {model_name}")
        else:
            _rembg_session = new_session(model_name)
            print(f"[rembg] CPU 세션 생성: {model_name}")
    return _rembg_session


# ═══════════════════════════════════════════════
# 1. 기본 처리
# ═══════════════════════════════════════════════

def median_smooth(image: np.ndarray, ksize: int = 5) -> np.ndarray:
    return cv2.medianBlur(image, ksize)

def detect_edges(image: np.ndarray, low: int = 50, high: int = 150) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    return cv2.Canny(blurred, low, high)


# ═══════════════════════════════════════════════
# 2. 배경 분리
# ═══════════════════════════════════════════════

def remove_bg_ai(image: np.ndarray, model_name: str = "u2net") -> dict | None:
    if not REMBG_AVAILABLE:
        return None
    try:
        from PIL import Image
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        session = get_rembg_session(model_name)
        result_pil = rembg_remove(pil_img, session=session)
        result_np = np.array(result_pil)
        if result_np.shape[2] == 4:
            alpha = result_np[:, :, 3]
            mask = (alpha > 128).astype(np.uint8) * 255
        else:
            return None
        return {"mask": mask}
    except Exception as e:
        print(f"[rembg] 실패: {e}")
        return None

def remove_bg_opencv(image: np.ndarray, ksize: int = 5) -> dict:
    smoothed = median_smooth(image, ksize)
    edges = detect_edges(smoothed)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {"mask": None}
    img_area = edges.shape[0] * edges.shape[1]
    valid = [c for c in contours if cv2.contourArea(c) > img_area * 0.01]
    largest = max(valid if valid else contours, key=cv2.contourArea)
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    hull = cv2.convexHull(largest)
    cv2.drawContours(mask, [hull], -1, 255, -1)
    k2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k2, iterations=3)
    return {"mask": mask}


# ═══════════════════════════════════════════════
# 3. 4꼭짓점 검출 + Perspective 보정
# ═══════════════════════════════════════════════

def find_quad_corners(mask: np.ndarray) -> np.ndarray | None:
    """
    마스크에서 사물의 4꼭짓점(사각형) 검출
    approxPolyDP로 다각형 근사 → 4점이면 그대로, 아니면 최소 외접 사각형
    Returns: 4x2 ndarray (꼭짓점 좌표) 또는 None
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    peri = cv2.arcLength(largest, True)

    # 다양한 epsilon으로 4꼭짓점 근사 시도
    for eps_mult in [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]:
        approx = cv2.approxPolyDP(largest, eps_mult * peri, True)
        if len(approx) == 4:
            return approx.reshape(4, 2).astype(np.float32)

    # 4점 근사 실패 → 최소 외접 회전 사각형
    rect = cv2.minAreaRect(largest)
    box = cv2.boxPoints(rect)
    return box.astype(np.float32)


def order_corners(pts: np.ndarray) -> np.ndarray:
    """
    4꼭짓점을 [좌상, 우상, 우하, 좌하] 순서로 정렬
    """
    # y좌표 기준 상위 2개, 하위 2개
    sorted_by_y = pts[np.argsort(pts[:, 1])]
    top_two = sorted_by_y[:2]
    bottom_two = sorted_by_y[2:]
    # 상위 중 x작은게 좌상
    tl, tr = top_two[np.argsort(top_two[:, 0])]
    bl, br = bottom_two[np.argsort(bottom_two[:, 0])]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def perspective_warp(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """
    4꼭짓점 기준으로 perspective 변환 → 정면 직사각형
    출력 크기는 실제 변의 길이로 계산
    """
    ordered = order_corners(corners)
    tl, tr, br, bl = ordered

    # 상변, 하변 길이
    w_top = np.linalg.norm(tr - tl)
    w_bottom = np.linalg.norm(br - bl)
    out_w = int(max(w_top, w_bottom))

    # 좌변, 우변 길이
    h_left = np.linalg.norm(bl - tl)
    h_right = np.linalg.norm(br - tr)
    out_h = int(max(h_left, h_right))

    # 최소 크기 보장
    out_w = max(out_w, 100)
    out_h = max(out_h, 100)

    dst = np.array([
        [0, 0],
        [out_w - 1, 0],
        [out_w - 1, out_h - 1],
        [0, out_h - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(ordered, dst)
    warped = cv2.warpPerspective(image, M, (out_w, out_h), flags=cv2.INTER_LANCZOS4)
    return warped


def draw_quad_on_image(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """검출된 4꼭짓점을 이미지에 시각화"""
    vis = image.copy()
    if corners is None:
        return vis

    ordered = order_corners(corners)
    pts = ordered.astype(int)

    # 사각형 그리기
    for i in range(4):
        p1 = tuple(pts[i])
        p2 = tuple(pts[(i + 1) % 4])
        cv2.line(vis, p1, p2, (0, 255, 0), 3, cv2.LINE_AA)

    # 꼭짓점 표시
    labels = ["TL", "TR", "BR", "BL"]
    for i, (label, pt) in enumerate(zip(labels, pts)):
        cv2.circle(vis, tuple(pt), 8, (0, 0, 255), -1)
        cv2.putText(vis, label, (pt[0] + 10, pt[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    return vis


# ═══════════════════════════════════════════════
# 4. 직선 검출 (시각화용)
# ═══════════════════════════════════════════════

def detect_lines(edges: np.ndarray, min_length: int = 50) -> list:
    lines_raw = cv2.HoughLinesP(edges, 1, np.pi / 180, 80,
                                 minLineLength=min_length, maxLineGap=10)
    if lines_raw is None:
        return []
    result = []
    for line in lines_raw:
        x1, y1, x2, y2 = line[0]
        length = math.hypot(x2 - x1, y2 - y1)
        result.append({"pt1": (int(x1), int(y1)), "pt2": (int(x2), int(y2)), "length": length})
    result.sort(key=lambda l: l["length"], reverse=True)
    return result

def draw_lines_on_image(image: np.ndarray, lines: list) -> np.ndarray:
    vis = image.copy()
    for line in lines[:20]:
        cv2.line(vis, line["pt1"], line["pt2"], (255, 150, 0), 1, cv2.LINE_AA)
    return vis


# ═══════════════════════════════════════════════
# 5. 통합 파이프라인
# ═══════════════════════════════════════════════

def process_image(image: np.ndarray, ksize: int = 5, use_ai: bool = True) -> dict:
    """
    전처리 파이프라인:
    1. 스무딩 → 2. 배경 분리(마스크) → 3. 4꼭짓점 검출
    → 4. Perspective 보정(정면 직사각형) → 5. 직선 시각화

    Returns: {
        "smoothed": 스무딩 결과,
        "edges": 엣지 검출,
        "lines_vis": 직선 검출 시각화,
        "mask": 배경 분리 마스크,
        "quad_vis": 4꼭짓점 검출 시각화,
        "warped": perspective 보정 결과 (핵심 출력),
        "separated": 배경 제거 이미지 (BGRA),
        "quad_found": bool,
        "method": "ai" | "opencv",
    }
    """
    # 1. 스무딩
    smoothed = median_smooth(image, ksize)

    # 2. 엣지 (시각화용)
    edges = detect_edges(smoothed)
    lines = detect_lines(edges)
    lines_vis = draw_lines_on_image(smoothed, lines)

    # 3. 배경 분리 → 마스크
    mask = None
    method_used = "opencv"

    if use_ai and REMBG_AVAILABLE:
        bg = remove_bg_ai(image)
        if bg and bg["mask"] is not None:
            mask = bg["mask"]
            method_used = "ai"

    if mask is None:
        bg = remove_bg_opencv(image, ksize)
        mask = bg.get("mask")

    # 4. 4꼭짓점 검출
    corners = None
    quad_found = False
    if mask is not None:
        corners = find_quad_corners(mask)
        if corners is not None:
            quad_found = True

    # 4꼭짓점 시각화
    quad_vis = draw_quad_on_image(image, corners)

    # 5. Perspective 보정
    warped = None
    if quad_found and corners is not None:
        warped = perspective_warp(image, corners)

    # 배경 제거 이미지 (BGRA)
    separated = None
    if mask is not None:
        bgra = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        bgra[:, :, 3] = mask
        separated = bgra

    # warped가 없으면 마스크 기반 크롭 fallback
    if warped is None and mask is not None:
        coords = cv2.findNonZero(mask)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            warped = image[y:y+h, x:x+w]

    # warped도 없으면 원본
    if warped is None:
        warped = image

    return {
        "smoothed": smoothed,
        "edges": edges,
        "lines_vis": lines_vis,
        "mask": mask,
        "quad_vis": quad_vis,
        "warped": warped,
        "separated": separated,
        "quad_found": quad_found,
        "contour_found": mask is not None,
        "line_count": len(lines),
        "method": method_used,
        "rembg_available": REMBG_AVAILABLE,
    }


def load_and_process(filepath: str, ksize: int = 5, use_ai: bool = True) -> dict:
    image = cv2.imread(filepath)
    if image is None:
        raise ValueError(f"이미지를 로드할 수 없습니다: {filepath}")
    return process_image(image, ksize, use_ai)
