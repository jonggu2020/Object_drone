"""
모듈 2: 파노라마 합성
- 특징점 검출 (ORB / SIFT)
- 특징점 매칭 (BFMatcher)
- 호모그래피 변환
- 이미지 정합 및 블렌딩

다른 모듈과의 의존성: 없음 (독립 모듈)
입력: 같은 면에서 촬영한 여러 장의 이미지 리스트
출력: 합성된 파노라마 이미지 (numpy array)
"""
import cv2
import numpy as np
from typing import Literal


def detect_features(
    image: np.ndarray,
    method: Literal["orb", "sift"] = "orb",
    max_features: int = 1000,
) -> tuple:
    """특징점 및 디스크립터 검출"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

    if method == "sift":
        detector = cv2.SIFT_create(nfeatures=max_features)
    else:
        detector = cv2.ORB_create(nfeatures=max_features)

    keypoints, descriptors = detector.detectAndCompute(gray, None)
    return keypoints, descriptors


def match_features(
    desc1: np.ndarray,
    desc2: np.ndarray,
    method: Literal["orb", "sift"] = "orb",
    ratio_thresh: float = 0.75,
) -> list:
    """두 이미지 간 특징점 매칭 (Lowe's ratio test)"""
    if desc1 is None or desc2 is None:
        return []

    if method == "sift":
        matcher = cv2.BFMatcher(cv2.NORM_L2)
    else:
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

    try:
        raw_matches = matcher.knnMatch(desc1, desc2, k=2)
    except cv2.error:
        return []

    good_matches = []
    for m_pair in raw_matches:
        if len(m_pair) == 2:
            m, n = m_pair
            if m.distance < ratio_thresh * n.distance:
                good_matches.append(m)

    return good_matches


def compute_homography(
    kp1: tuple,
    kp2: tuple,
    matches: list,
    min_matches: int = 10,
) -> np.ndarray | None:
    """매칭된 특징점으로 호모그래피 행렬 계산"""
    if len(matches) < min_matches:
        return None

    src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    return H


def warp_and_blend(
    img1: np.ndarray,
    img2: np.ndarray,
    H: np.ndarray,
) -> np.ndarray:
    """호모그래피 변환 후 두 이미지 블렌딩"""
    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]

    # img1의 네 꼭짓점을 변환하여 출력 캔버스 크기 결정
    corners1 = np.float32([[0, 0], [w1, 0], [w1, h1], [0, h1]]).reshape(-1, 1, 2)
    corners2 = np.float32([[0, 0], [w2, 0], [w2, h2], [0, h2]]).reshape(-1, 1, 2)
    warped_corners = cv2.perspectiveTransform(corners1, H)

    all_corners = np.concatenate([warped_corners, corners2], axis=0)
    x_min, y_min = np.int32(all_corners.min(axis=0).ravel())
    x_max, y_max = np.int32(all_corners.max(axis=0).ravel())

    # 오프셋 적용 (음수 좌표 처리)
    offset = np.array([[1, 0, -x_min], [0, 1, -y_min], [0, 0, 1]], dtype=np.float64)
    canvas_w = x_max - x_min
    canvas_h = y_max - y_min

    # 캔버스 크기 제한 (메모리 보호)
    max_dim = 8000
    if canvas_w > max_dim or canvas_h > max_dim:
        scale = max_dim / max(canvas_w, canvas_h)
        canvas_w = int(canvas_w * scale)
        canvas_h = int(canvas_h * scale)

    warped1 = cv2.warpPerspective(img1, offset @ H, (canvas_w, canvas_h))

    # img2를 캔버스에 배치
    result = warped1.copy()
    y_off, x_off = -y_min, -x_min
    roi = result[y_off : y_off + h2, x_off : x_off + w2]

    # 겹치는 영역은 가중 평균 블렌딩
    mask_warped = cv2.cvtColor(warped1[y_off : y_off + h2, x_off : x_off + w2], cv2.COLOR_BGR2GRAY) > 0
    mask_img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY) > 0
    overlap = mask_warped & mask_img2

    blended = roi.copy()
    blended[~mask_warped] = img2[~mask_warped]
    if np.any(overlap):
        blended[overlap] = cv2.addWeighted(roi, 0.5, img2, 0.5, 0)[overlap]
    result[y_off : y_off + h2, x_off : x_off + w2] = blended

    return result


def stitch_images(
    images: list[np.ndarray],
    method: Literal["orb", "sift"] = "orb",
) -> dict:
    """
    여러 이미지를 순차적으로 파노라마 합성
    Returns: {
        "panorama": 합성 결과 이미지,
        "match_counts": 각 단계별 매칭 수,
        "success": bool
    }
    """
    if not images:
        return {"panorama": None, "match_counts": [], "success": False}

    if len(images) == 1:
        return {"panorama": images[0], "match_counts": [], "success": True}

    result = images[0]
    match_counts = []

    for i in range(1, len(images)):
        kp1, desc1 = detect_features(result, method)
        kp2, desc2 = detect_features(images[i], method)
        matches = match_features(desc1, desc2, method)
        match_counts.append(len(matches))

        H = compute_homography(kp1, kp2, matches)
        if H is None:
            # 매칭 실패 시 단순 수평 이어 붙이기 (fallback)
            h1, h2_ = result.shape[0], images[i].shape[0]
            max_h = max(h1, h2_)
            pad1 = np.zeros((max_h - h1, result.shape[1], 3), dtype=np.uint8)
            pad2 = np.zeros((max_h - h2_, images[i].shape[1], 3), dtype=np.uint8)
            result = np.hstack([
                np.vstack([result, pad1]),
                np.vstack([images[i], pad2]),
            ])
            continue

        result = warp_and_blend(result, images[i], H)

    return {
        "panorama": result,
        "match_counts": match_counts,
        "success": True,
    }


def normalize_sizes(images: list[np.ndarray], target_height: int = 800) -> list[np.ndarray]:
    """이미지들의 높이를 통일하여 비율/크기 정규화"""
    normalized = []
    for img in images:
        h, w = img.shape[:2]
        if h == target_height:
            normalized.append(img)
            continue
        scale = target_height / h
        new_w = int(w * scale)
        resized = cv2.resize(img, (new_w, target_height), interpolation=cv2.INTER_LANCZOS4)
        normalized.append(resized)
    return normalized
