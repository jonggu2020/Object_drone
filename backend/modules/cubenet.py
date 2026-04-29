"""
모듈 3: 주사위 전개도 구성 (v4 - 밀착 배치)

핵심:
- 면 사이 간격 0px (빈틈 없이 밀착)
- 전면 기준 공유 변 정규화 (비율 유지)
- 밑면 = 전면과 같은 크기의 빈 면 (X 표시)
- BGRA 투명 배경

레이아웃:
           [ front ]
  [left][ 밑면X ][right][back]
           [  top  ]

공유 변 규칙:
  front  → 기준 (w_f × h_f)
  top    너비 = front 너비       (front 아래에 붙음)
  left   높이 = front 높이       (밑면X 좌측)
  right  높이 = front 높이       (밑면X 우측)
  back   높이 = right 높이       (right 우측)
  밑면X  크기 = front와 동일     (가운데 빈 면)
"""
import cv2
import numpy as np


def ensure_bgra(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2BGRA)
    elif image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    return image.copy()


def resize_by_width(image: np.ndarray, target_w: int) -> np.ndarray:
    """너비 기준 비율 유지 리사이즈"""
    h, w = image.shape[:2]
    scale = target_w / w
    return cv2.resize(image, (target_w, int(h * scale)), interpolation=cv2.INTER_LANCZOS4)


def resize_by_height(image: np.ndarray, target_h: int) -> np.ndarray:
    """높이 기준 비율 유지 리사이즈"""
    h, w = image.shape[:2]
    scale = target_h / h
    return cv2.resize(image, (int(w * scale), target_h), interpolation=cv2.INTER_LANCZOS4)


def create_cube_net(face_images: dict[str, np.ndarray]) -> dict:
    """
    적응형 전개도 구성 — 빈틈 없이 밀착 배치

    Returns: {
        "net_image": BGRA 전개도,
        "face_rects": {name: (x, y, w, h)},
        "faces_used": [],
        "missing_faces": [],
        "front_size": (w, h),
    }
    """
    # ── 1. 전면 기준 정규화 ──
    if "front" not in face_images:
        # front 없으면 첫 번째 면을 기준으로
        first_key = next(iter(face_images))
        face_images["front"] = face_images[first_key]

    front = ensure_bgra(face_images["front"])
    f_h, f_w = front.shape[:2]

    faces = {"front": front}

    if "top" in face_images:
        faces["top"] = resize_by_width(ensure_bgra(face_images["top"]), f_w)

    if "left" in face_images:
        faces["left"] = resize_by_height(ensure_bgra(face_images["left"]), f_h)

    if "right" in face_images:
        faces["right"] = resize_by_height(ensure_bgra(face_images["right"]), f_h)

    if "back" in face_images:
        ref_h = faces["right"].shape[0] if "right" in faces else f_h
        faces["back"] = resize_by_height(ensure_bgra(face_images["back"]), ref_h)

    # ── 2. 크기 수집 ──
    def dim(name):
        if name in faces:
            return faces[name].shape[1], faces[name].shape[0]
        return 0, 0

    fw, fh = dim("front")
    tw, th = dim("top")
    lw, lh = dim("left")
    rw, rh = dim("right")
    bw, bh = dim("back")

    # 밑면X = front와 같은 크기
    bottom_w, bottom_h = fw, fh

    # ── 3. 캔버스 좌표 계산 (빈틈 0px) ──
    #
    #   Row 0:           [ front ]              시작 x = left_w
    #   Row 1: [left][ 밑면X ][right][back]     시작 y = fh
    #   Row 2:           [  top  ]              시작 x = left_w, y = fh + fh
    #
    # mid row height = fh (front 높이 = left/right 높이)

    mid_y = fh          # Row 1 시작 y
    bot_y = fh + fh     # Row 2 시작 y

    # left 시작 x = 0
    # 밑면X 시작 x = lw
    center_x = lw if lw > 0 else 0
    # front 시작 x = center_x (밑면X 위에)
    # right 시작 x = center_x + fw
    right_x = center_x + fw
    # back 시작 x = right_x + rw
    back_x = right_x + rw if rw > 0 else right_x

    # 캔버스 크기
    canvas_w = max(
        center_x + fw,                          # front/top 우측 끝
        back_x + bw if bw > 0 else right_x + rw,  # back 우측 끝
        lw + fw + rw + bw,                      # mid row 전체
    )
    canvas_h = bot_y + th if th > 0 else bot_y

    # left가 없는 경우 center_x 보정
    if lw == 0:
        # left 없으면 front를 x=0에 배치
        center_x = 0
        right_x = fw
        back_x = fw + rw if rw > 0 else fw
        canvas_w = max(fw, back_x + bw)

    canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
    face_rects = {}
    faces_used = []
    missing = []

    # ── 4. 면 배치 (밀착) ──

    # front (Row 0)
    _paste(canvas, faces["front"], center_x, 0)
    face_rects["front"] = (center_x, 0, fw, fh)
    faces_used.append("front")

    # left (Row 1)
    if "left" in faces:
        _paste(canvas, faces["left"], center_x - lw, mid_y)
        face_rects["left"] = (center_x - lw, mid_y, lw, lh)
        faces_used.append("left")
    else:
        missing.append("left")

    # 밑면X (Row 1, center) — 반투명 회색 + X 표시
    bottom_placeholder = np.zeros((bottom_h, bottom_w, 4), dtype=np.uint8)
    bottom_placeholder[:, :] = [60, 60, 60, 180]
    # X 글자
    cv2.putText(bottom_placeholder, "X", (bottom_w // 2 - 30, bottom_h // 2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 2.5, (120, 120, 120, 255), 4, cv2.LINE_AA)
    _paste(canvas, bottom_placeholder, center_x, mid_y)
    face_rects["bottom"] = (center_x, mid_y, bottom_w, bottom_h)

    # right (Row 1)
    if "right" in faces:
        _paste(canvas, faces["right"], center_x + fw, mid_y)
        face_rects["right"] = (center_x + fw, mid_y, rw, rh)
        faces_used.append("right")
    else:
        missing.append("right")

    # back (Row 1)
    if "back" in faces:
        bx = center_x + fw + rw if rw > 0 else center_x + fw
        _paste(canvas, faces["back"], bx, mid_y)
        face_rects["back"] = (bx, mid_y, bw, bh)
        faces_used.append("back")
    else:
        missing.append("back")

    # top (Row 2)
    if "top" in faces:
        _paste(canvas, faces["top"], center_x, bot_y)
        face_rects["top"] = (center_x, bot_y, tw, th)
        faces_used.append("top")
    else:
        missing.append("top")

    # ── 5. 트리밍 ──
    canvas = _trim_transparent(canvas, margin=0)

    return {
        "net_image": canvas,
        "face_rects": face_rects,
        "faces_used": faces_used,
        "missing_faces": missing,
        "front_size": (fw, fh),
    }


def _paste(canvas: np.ndarray, image: np.ndarray, x: int, y: int):
    """BGRA 이미지를 캔버스에 붙이기"""
    if x < 0 or y < 0:
        # 음수 좌표면 이미지 크롭
        ix = max(0, -x)
        iy = max(0, -y)
        x = max(0, x)
        y = max(0, y)
        image = image[iy:, ix:]

    h, w = image.shape[:2]
    ch, cw = canvas.shape[:2]
    x2 = min(x + w, cw)
    y2 = min(y + h, ch)
    wa = x2 - x
    ha = y2 - y
    if wa <= 0 or ha <= 0:
        return
    canvas[y:y2, x:x2] = image[:ha, :wa]


def _trim_transparent(image: np.ndarray, margin: int = 0) -> np.ndarray:
    """투명하지 않은 영역만 남기고 트리밍"""
    if len(image.shape) < 3 or image.shape[2] < 4:
        return image
    alpha = image[:, :, 3]
    coords = cv2.findNonZero(alpha)
    if coords is None:
        return image
    x, y, w, h = cv2.boundingRect(coords)
    x1 = max(0, x - margin)
    y1 = max(0, y - margin)
    x2 = min(image.shape[1], x + w + margin)
    y2 = min(image.shape[0], y + h + margin)
    return image[y1:y2, x1:x2]


def draw_fold_guides(
    net_image: np.ndarray,
    face_rects: dict,
    color: tuple = (0, 180, 255, 255),
) -> np.ndarray:
    """면 경계에 접는선 가이드 (점선)"""
    result = net_image.copy()
    for name, (x, y, w, h) in face_rects.items():
        cv2.rectangle(result, (x, y), (x + w - 1, y + h - 1), color, 1, cv2.LINE_AA)
    return result
