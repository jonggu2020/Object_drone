"""
모듈 4: 3D 복원 (v5.3)

핵심 변경:
  1. 4변 + 4꼭짓점 독립 판정
     - 각 변(edge): 직선/곡면 개별 판정
     - 각 꼭짓점(vertex): 직각/곡선 개별 판정
     - 변=직선 + 꼭짓점=곡선 조합 가능
  2. 밑면에 상단 이미지 적용 (6면 텍스처)
  3. GPU 전처리 지원 플래그
"""
import cv2
import numpy as np
from pathlib import Path
import math

try:
    from scipy.interpolate import splprep, splev
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# ═══════════════════════════════════════════════
# 1. 윤곽 추출 + 형상 분류
# ═══════════════════════════════════════════════

def extract_contour(mask, threshold=128):
    if mask.dtype == bool:
        binary = mask.astype(np.uint8) * 255
    elif mask.max() <= 1:
        binary = (mask * 255).astype(np.uint8)
    else:
        binary = mask.copy()
    _, thresh = cv2.threshold(binary, threshold, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 100:
        return None
    x, y, w, h = cv2.boundingRect(largest)
    peri = cv2.arcLength(largest, True)
    smooth = cv2.approxPolyDP(largest, 0.005 * peri, True)
    clean = np.zeros_like(thresh)
    cv2.drawContours(clean, [smooth], -1, 255, -1)
    return {
        "contour": largest, "contour_smooth": smooth,
        "silhouette": clean[y:y+h, x:x+w] > 128,
        "bbox": (x, y, w, h), "width": w, "height": h,
        "perimeter": peri, "area": cv2.contourArea(largest),
    }


def classify_shape(info):
    contour = info["contour"]
    area, w, h, peri = info["area"], info["width"], info["height"], info["perimeter"]
    fill = area / (w * h) if w * h > 0 else 0
    approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
    nv = len(approx)
    circ = (4 * math.pi * area) / (peri * peri) if peri > 0 else 0
    is_rect = nv <= 6 and fill > 0.82 and circ < 0.85
    t = "rectangle" if is_rect else "curved"
    print(f"[classify] nv={nv} fill={fill:.3f} circ={circ:.3f} → {t}")
    return {"type": t, "fill_ratio": fill, "vertex_count": nv, "circularity": round(circ, 3)}


# ═══════════════════════════════════════════════
# 2-A. 직사각형 → 24정점 직육면체 (6면 텍스처)
# ═══════════════════════════════════════════════

def build_box_mesh(proportions):
    rx, ry, rz = proportions["ratio_x"], proportions["ratio_y"], proportions["ratio_z"]
    hx, hy, hz = rx/2, ry/2, rz/2
    verts, uvs, fids = [], [], []

    def add_face(v0, v1, v2, v3, fid):
        b = len(verts)
        verts.extend([v0, v1, v2, v3])
        uvs.extend([[0,0],[1,0],[1,1],[0,1]])
        fids.extend([fid]*4)
        return b

    b=add_face([-hx,-hy,hz],[hx,-hy,hz],[hx,hy,hz],[-hx,hy,hz],0)       # front
    t_f=[[b,b+1,b+2],[b,b+2,b+3]]
    b=add_face([hx,-hy,-hz],[-hx,-hy,-hz],[-hx,hy,-hz],[hx,hy,-hz],1)    # back
    t_b=[[b,b+1,b+2],[b,b+2,b+3]]
    b=add_face([-hx,-hy,-hz],[-hx,-hy,hz],[-hx,hy,hz],[-hx,hy,-hz],2)    # left
    t_l=[[b,b+1,b+2],[b,b+2,b+3]]
    b=add_face([hx,-hy,hz],[hx,-hy,-hz],[hx,hy,-hz],[hx,hy,hz],3)        # right
    t_r=[[b,b+1,b+2],[b,b+2,b+3]]
    b=add_face([-hx,hy,hz],[hx,hy,hz],[hx,hy,-hz],[-hx,hy,-hz],4)        # top
    t_t=[[b,b+1,b+2],[b,b+2,b+3]]
    b=add_face([-hx,-hy,-hz],[hx,-hy,-hz],[hx,-hy,hz],[-hx,-hy,hz],5)    # bottom (=top 이미지 적용)
    t_bt=[[b,b+1,b+2],[b,b+2,b+3]]

    vertices = np.array(verts, dtype=np.float32)
    faces = np.array(t_f+t_b+t_l+t_r+t_t+t_bt, dtype=np.int32)
    return {
        "vertices": vertices, "faces": faces,
        "normals": compute_normals(vertices, faces),
        "uvs": np.array(uvs, dtype=np.float32),
        "face_texture_ids": np.array(fids, dtype=np.int32),
        "shape_type": "rectangle",
    }


# ═══════════════════════════════════════════════
# 2-B. 곡면: 4변+4꼭짓점 독립 판정
# ═══════════════════════════════════════════════

def find_4_corners(contour):
    """contour에서 4개 주요 꼭짓점 검출"""
    pts = contour.reshape(-1, 2).astype(float)
    peri = cv2.arcLength(contour, True)

    # 다양한 epsilon으로 4점 찾기
    for eps in [0.02, 0.03, 0.04, 0.05, 0.06, 0.08]:
        approx = cv2.approxPolyDP(contour, eps * peri, True)
        if len(approx) == 4:
            return approx.reshape(4, 2)

    # 4점 실패 → minAreaRect
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    return box.astype(float)


def order_corners_clockwise(corners):
    """4꼭짓점을 시계 방향으로 정렬 (좌상부터)"""
    cx, cy = corners.mean(axis=0)
    angles = np.arctan2(corners[:, 1] - cy, corners[:, 0] - cx)
    order = np.argsort(angles)
    return corners[order]


def analyze_edges_and_vertices(contour, corners):
    """
    4변 + 4꼭짓점 독립 판정

    Returns: {
        "edges": [{"straight": bool, "curve_strength": float}, ...] × 4,
        "vertices": [{"sharp": bool, "curve_strength": float}, ...] × 4,
    }
    """
    pts = contour.reshape(-1, 2).astype(float)
    n_pts = len(pts)

    EDGE_THRESHOLD = 0.05    # 5%: 변의 곡선 판정
    VERTEX_RADIUS_PCT = 0.08  # 꼭짓점 주변 8% 범위

    # 각 꼭짓점에 가장 가까운 인덱스
    corner_indices = []
    for c in corners:
        dists = np.linalg.norm(pts - c, axis=1)
        corner_indices.append(np.argmin(dists))

    # ── 4변 분석 ──
    edges = []
    for i in range(4):
        i_start = corner_indices[i]
        i_end = corner_indices[(i + 1) % 4]

        # 구간 점 추출 (순환)
        if i_end > i_start:
            seg = pts[i_start:i_end+1]
        else:
            seg = np.vstack([pts[i_start:], pts[:i_end+1]])

        if len(seg) < 2:
            edges.append({"straight": True, "curve_strength": 0.0, "points": seg})
            continue

        p0, p1 = seg[0], seg[-1]
        seg_len = np.linalg.norm(p1 - p0)
        if seg_len < 1:
            edges.append({"straight": True, "curve_strength": 0.0, "points": seg})
            continue

        # 직선 이탈 계산 (중간 80% 구간만 — 꼭짓점 근처 제외)
        seg_dir = (p1 - p0) / seg_len
        n_seg = len(seg)
        start_idx = max(1, int(n_seg * 0.1))
        end_idx = min(n_seg - 1, int(n_seg * 0.9))
        mid_seg = seg[start_idx:end_idx]

        if len(mid_seg) < 2:
            edges.append({"straight": True, "curve_strength": 0.0, "points": seg})
            continue

        devs = []
        for p in mid_seg:
            proj = np.dot(p - p0, seg_dir)
            closest = p0 + proj * seg_dir
            devs.append(np.linalg.norm(p - closest))

        max_dev = max(devs) if devs else 0
        strength = max_dev / seg_len

        edges.append({
            "straight": strength < EDGE_THRESHOLD,
            "curve_strength": strength,
            "points": seg,
        })

    # ── 4꼭짓점 분석 ──
    vertices_info = []
    peri = cv2.arcLength(contour, True)
    radius = peri * VERTEX_RADIUS_PCT

    for i in range(4):
        ci = corner_indices[i]
        corner_pt = pts[ci]

        # 꼭짓점 주변 점 수집
        nearby = []
        for j in range(n_pts):
            if np.linalg.norm(pts[j] - corner_pt) < radius:
                nearby.append(pts[j])

        if len(nearby) < 3:
            vertices_info.append({"sharp": True, "curve_strength": 0.0})
            continue

        nearby = np.array(nearby)
        # 전후 점으로 각도 계산
        prev_pt = pts[(ci - int(n_pts * 0.05)) % n_pts]
        next_pt = pts[(ci + int(n_pts * 0.05)) % n_pts]

        v1 = prev_pt - corner_pt
        v2 = next_pt - corner_pt
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
        angle = math.degrees(math.acos(np.clip(cos_angle, -1, 1)))

        # 직각(90°)에 가까우면 sharp, 멀면 curved
        angle_dev = abs(angle - 90)

        # 주변 점들의 곡률: 직각이면 꺾이고 곡선이면 부드러움
        # 이상적 직각 경로 vs 실제 경로의 차이
        ideal_dist = np.linalg.norm(prev_pt - corner_pt) + np.linalg.norm(next_pt - corner_pt)
        arc_dist = 0
        for j in range(len(nearby) - 1):
            arc_dist += np.linalg.norm(nearby[j+1] - nearby[j])

        # 직각이면 arc_dist ≈ ideal_dist, 곡선이면 arc_dist < ideal_dist
        curve_ratio = arc_dist / ideal_dist if ideal_dist > 0 else 1

        is_sharp = angle_dev < 25 and curve_ratio > 0.85
        v_strength = 1.0 - min(curve_ratio, 1.0)

        vertices_info.append({
            "sharp": is_sharp,
            "curve_strength": v_strength,
            "angle": angle,
        })

    for i, e in enumerate(edges):
        print(f"    [edge {i}] {'직선' if e['straight'] else '곡면'} (편차 {e['curve_strength']*100:.1f}%)")
    for i, v in enumerate(vertices_info):
        print(f"    [vtx  {i}] {'직각' if v['sharp'] else '곡선'} (강도 {v['curve_strength']*100:.1f}%)")

    return {"edges": edges, "vertices": vertices_info, "corners": corners, "corner_indices": corner_indices}


def build_smart_contour(contour, analysis, n_points=64):
    """
    4변+4꼭짓점 판정 결과로 최종 윤곽 점 생성
    - 직선 변 → 양 끝 직선 보간
    - 곡면 변 → Spline 보간
    - 직각 꼭짓점 → 꼭짓점 그대로
    - 곡선 꼭짓점 → 주변 Spline 보간
    """
    edges = analysis["edges"]
    vertices = analysis["vertices"]
    corners = analysis["corners"]

    pts_per_edge = n_points // 4
    pts_per_corner = max(4, n_points // 16)  # 꼭짓점당 보간 점 수
    result = []

    for i in range(4):
        edge = edges[i]
        vtx_start = vertices[i]
        vtx_end = vertices[(i + 1) % 4]
        seg = edge["points"]

        if len(seg) < 2:
            continue

        p0, p1 = seg[0], seg[-1]

        # ── 시작 꼭짓점 처리 ──
        if not vtx_start["sharp"]:
            # 곡선 꼭짓점: 진입부를 Spline으로
            n_corner_pts = min(pts_per_corner, len(seg) // 4)
            corner_seg = seg[:max(3, n_corner_pts)]
            if SCIPY_AVAILABLE and len(corner_seg) > 3:
                try:
                    tck, u = splprep([corner_seg[:, 0], corner_seg[:, 1]], s=len(corner_seg)*0.05, per=False)
                    u_new = np.linspace(0, 1, pts_per_corner, endpoint=False)
                    xn, yn = splev(u_new, tck)
                    for x, y in zip(xn, yn):
                        result.append([x, y])
                    seg = seg[n_corner_pts:]  # 나머지 처리용
                    if len(seg) > 0:
                        p0 = seg[0]
                except Exception:
                    result.append(p0.tolist())
            else:
                result.append(p0.tolist())
        else:
            result.append(p0.tolist())

        # ── 변 본체 처리 ──
        if edge["straight"]:
            # 직선 보간
            if len(seg) >= 2:
                p0_e, p1_e = seg[0], seg[-1]
                for t in np.linspace(0, 1, pts_per_edge, endpoint=False)[1:]:
                    result.append((p0_e * (1 - t) + p1_e * t).tolist())
        else:
            # 곡면: 원본 형태에 충실한 Spline (smoothing 최소화)
            if SCIPY_AVAILABLE and len(seg) > 3:
                try:
                    tck, u = splprep([seg[:, 0], seg[:, 1]], s=len(seg)*0.05, per=False)
                    u_new = np.linspace(0, 1, pts_per_edge, endpoint=False)[1:]
                    xn, yn = splev(u_new, tck)
                    for x, y in zip(xn, yn):
                        result.append([x, y])
                except Exception:
                    for t in np.linspace(0, 1, pts_per_edge, endpoint=False)[1:]:
                        idx = int(t * (len(seg) - 1))
                        result.append(seg[idx].tolist())
            else:
                for t in np.linspace(0, 1, pts_per_edge, endpoint=False)[1:]:
                    idx = int(t * (len(seg) - 1))
                    result.append(seg[idx].tolist())

    result = np.array(result, dtype=float)

    # 최종 n_points 리샘플
    if len(result) < 4:
        return result

    if len(result) > n_points:
        indices = np.linspace(0, len(result)-1, n_points).astype(int)
        result = result[indices]
    elif len(result) < n_points:
        indices = np.linspace(0, len(result)-1, n_points)
        ii = np.minimum(indices.astype(int), len(result) - 2)
        frac = indices - ii
        result = result[ii] * (1 - frac[:, None]) + result[np.minimum(ii + 1, len(result)-1)] * frac[:, None]

    return result


# ═══════════════════════════════════════════════
# 높이 프로파일 + 곡면 메시 생성
# ═══════════════════════════════════════════════

def extract_height_profile(region, clamp_range=0.15):
    sil = region["silhouette"]
    h, w = sil.shape
    widths = np.zeros(h)
    for y in range(h):
        nz = np.where(sil[y, :])[0]
        if len(nz) > 0:
            widths[y] = (nz[-1] - nz[0] + 1) / w
    widths = widths[::-1]
    if len(widths) == 0 or np.max(widths) == 0:
        return np.ones(h)
    med = np.median(widths[widths > 0])
    if med <= 0: med = 1.0
    norm = widths / med
    return np.clip(norm, 1.0 - clamp_range, 1.0 + clamp_range)


def build_curved_mesh(top_contour, top_bbox, regions, proportions, n_profile=32, n_contour=96):
    rx, ry, rz = proportions["ratio_x"], proportions["ratio_y"], proportions["ratio_z"]

    # 1. 4꼭짓점 검출 + 독립 판정
    corners = find_4_corners(top_contour)
    corners = order_corners_clockwise(corners)
    analysis = analyze_edges_and_vertices(top_contour, corners)

    # 2. 판정 결과로 스마트 윤곽 생성
    smart_pts = build_smart_contour(top_contour, analysis, n_contour)

    if len(smart_pts) < 4:
        # fallback
        pts = top_contour.reshape(-1, 2).astype(float)
        indices = np.linspace(0, len(pts)-1, n_contour).astype(int)
        smart_pts = pts[indices]

    # 중심/범위
    cx = (smart_pts[:, 0].max() + smart_pts[:, 0].min()) / 2
    cy = (smart_pts[:, 1].max() + smart_pts[:, 1].min()) / 2
    rx_range = max(smart_pts[:, 0].max() - smart_pts[:, 0].min(), 1)
    ry_range = max(smart_pts[:, 1].max() - smart_pts[:, 1].min(), 1)

    norm_pts = np.zeros_like(smart_pts)
    norm_pts[:, 0] = (smart_pts[:, 0] - cx) / rx_range * rx
    norm_pts[:, 1] = (smart_pts[:, 1] - cy) / ry_range * rz

    # 3. 프로파일
    profile = np.ones(n_profile)
    if "front" in regions:
        profile = extract_height_profile(regions["front"], 0.15)
    elif "left" in regions:
        profile = extract_height_profile(regions["left"], 0.15)
    profile_r = np.interp(np.linspace(0, len(profile)-1, n_profile), np.arange(len(profile)), profile)

    # 4. 단면 스택
    n_c = len(norm_pts)
    vertices = []
    for hi in range(n_profile):
        y_val = (hi / max(n_profile - 1, 1) - 0.5) * ry
        scale = profile_r[hi]
        for pi in range(n_c):
            vertices.append([norm_pts[pi, 0] * scale, y_val, norm_pts[pi, 1] * scale])

    top_ci = len(vertices)
    vertices.append([0, 0.5 * ry, 0])
    bot_ci = len(vertices)
    vertices.append([0, -0.5 * ry, 0])
    vertices = np.array(vertices, dtype=np.float32)

    # 5. 삼각형
    faces = []
    for hi in range(n_profile - 1):
        for pi in range(n_c):
            c = hi * n_c + pi
            cn = hi * n_c + (pi + 1) % n_c
            u = (hi + 1) * n_c + pi
            un = (hi + 1) * n_c + (pi + 1) % n_c
            faces.append([c, cn, un])
            faces.append([c, un, u])

    # 캡 (상단 + 하단)
    tr = (n_profile - 1) * n_c
    for pi in range(n_c):
        faces.append([tr + pi, tr + (pi+1) % n_c, top_ci])
    for pi in range(n_c):
        faces.append([(pi+1) % n_c, pi, bot_ci])

    faces = np.array(faces, dtype=np.int32)
    normals = compute_normals(vertices, faces)

    # 6. UV + 면 할당 (각도 기반 + 밑면 포함)
    uvs = np.zeros((len(vertices), 2), dtype=np.float32)
    fti = np.zeros(len(vertices), dtype=np.int32)

    for i in range(len(vertices)):
        vx, vy, vz = vertices[i]
        angle = math.degrees(math.atan2(vz, vx))
        if angle < 0: angle += 360

        if 45 <= angle < 135:
            fti[i] = 0  # front
            uvs[i] = [(vx/rx)+0.5, (vy/ry)+0.5]
        elif 135 <= angle < 225:
            fti[i] = 2  # left
            uvs[i] = [(-vz/rz)+0.5, (vy/ry)+0.5]
        elif 225 <= angle < 315:
            fti[i] = 1  # back
            uvs[i] = [(-vx/rx)+0.5, (vy/ry)+0.5]
        else:
            fti[i] = 3  # right
            uvs[i] = [(vz/rz)+0.5, (vy/ry)+0.5]

    # top/bottom (법선 기반)
    for i in range(len(vertices)):
        n = normals[i]
        if abs(n[1]) > 0.7:
            fti[i] = 4 if n[1] > 0 else 5  # 5 = bottom (상단 이미지 적용)
            uvs[i] = [(vertices[i,0]/rx)+0.5, (vertices[i,2]/rz)+0.5]

    uvs = np.clip(uvs, 0, 1)

    return {
        "vertices": vertices, "faces": faces,
        "normals": normals, "uvs": uvs,
        "face_texture_ids": fti, "shape_type": "curved",
    }


# ═══════════════════════════════════════════════
# 공통 함수
# ═══════════════════════════════════════════════

def compute_normals(vertices, faces):
    normals = np.zeros_like(vertices)
    for f in faces:
        v0, v1, v2 = vertices[f[0]], vertices[f[1]], vertices[f[2]]
        n = np.cross(v1 - v0, v2 - v0)
        ln = np.linalg.norm(n)
        if ln > 0: n /= ln
        normals[f[0]] += n; normals[f[1]] += n; normals[f[2]] += n
    for i in range(len(normals)):
        ln = np.linalg.norm(normals[i])
        if ln > 0: normals[i] /= ln
    return normals.astype(np.float32)


def sync_proportions(regions):
    x, y, z = [], [], []
    for d in ("front","back"):
        if d in regions: x.append(regions[d]["width"]); y.append(regions[d]["height"])
    for d in ("left","right"):
        if d in regions: z.append(regions[d]["width"]); y.append(regions[d]["height"])
    if "top" in regions: x.append(regions["top"]["width"]); z.append(regions["top"]["height"])
    ax = np.mean(x) if x else 1; ay = np.mean(y) if y else 1
    az = np.mean(z) if z else (np.mean(x) if x else 1)
    m = max(ax, ay, az)
    return {"ratio_x": ax/m, "ratio_y": ay/m, "ratio_z": az/m}


def export_obj(mesh, filepath, scale=1.0):
    v = mesh["vertices"] * scale; f = mesh["faces"]
    lines = [f"# 3D Model V:{len(v)} F:{len(f)}", ""]
    for p in v: lines.append(f"v {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}")
    if "uvs" in mesh:
        lines.append("")
        for uv in mesh["uvs"]: lines.append(f"vt {uv[0]:.6f} {uv[1]:.6f}")
    if "normals" in mesh:
        lines.append("")
        for n in mesh["normals"]: lines.append(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}")
    lines.append("")
    for t in f:
        lines.append(f"f {t[0]+1}/{t[0]+1}/{t[0]+1} {t[1]+1}/{t[1]+1}/{t[1]+1} {t[2]+1}/{t[2]+1}/{t[2]+1}")
    Path(filepath).write_text("\n".join(lines))


# ═══════════════════════════════════════════════
# 통합 파이프라인
# ═══════════════════════════════════════════════

def reconstruct_3d(silhouettes, resolution=128, smooth=True):
    regions = {}
    for d, mask in silhouettes.items():
        if mask is None: continue
        info = extract_contour(mask)
        if info: regions[d] = info; print(f"[recon] {d}: {info['width']}×{info['height']}")
    if len(regions) < 2:
        return {"error": "실루엣 부족", "mesh": None}

    target = regions.get("top", regions.get("front"))
    shape_info = classify_shape(target)
    proportions = sync_proportions(regions)
    print(f"[recon] 비율 X={proportions['ratio_x']:.3f} Y={proportions['ratio_y']:.3f} Z={proportions['ratio_z']:.3f}")

    if shape_info["type"] == "rectangle":
        mesh = build_box_mesh(proportions)
    else:
        top = regions.get("top")
        if top:
            # 원본 contour 사용 (approxPolyDP 근사 대신 — 형태 손실 방지)
            mesh = build_curved_mesh(top["contour"], top["bbox"], regions, proportions)
        else:
            mesh = build_box_mesh(proportions)
            shape_info["type"] = "rectangle (fallback)"

    print(f"[recon] {shape_info['type']}: V={len(mesh['vertices'])} F={len(mesh['faces'])}")
    return {
        "mesh": mesh, "shape_type": shape_info["type"], "shape_info": shape_info,
        "voxel_count": 0, "fill_ratio": 0, "resolution": resolution,
        "proportions": {k: round(v,3) for k,v in proportions.items()},
        "directions_used": list(regions.keys()),
    }
