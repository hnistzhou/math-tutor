#!/usr/bin/env python3
"""
check_layout.py - 通用 Manim 帧布局质量检测
适用于任意 1280×720 Manim 渲染帧（黑底），不依赖题目类型或帧类型。

检测三项：
1. edge_proximity  - 内容距四边框是否过近（< 30px）
2. border_clipping - 边框条带内是否有大量内容像素（> 50px）
3. overlap_hotspots - 80px 网格中是否有相邻高密度格子对（≥ 2 对）

用法：
  python scripts/check_layout.py --image /tmp/keyframe_5.png --frame-id 5
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

# ─── 常量 ───────────────────────────────────────────────────────────────────
TARGET_W = 1280
TARGET_H = 720
CONTENT_THRESHOLD = 15        # 亮度 ≥ 15 视为有内容（黑底帧）
EDGE_MARGIN = 30              # 内容距边框警戒距离（px）
BORDER_STRIP = 30             # 边框条带宽度（px）
BORDER_PIXEL_LIMIT = 50       # 边框条带内内容像素数上限
GRID_SIZE = 80                # 热点检测网格尺寸（px）
DENSITY_THRESHOLD = 0.12      # 格子内容像素占比阈值，超过即为热点
ADJACENT_PAIR_LIMIT = 2       # 相邻热点对数警戒值


# ─── 图像加载 ─────────────────────────────────────────────────────────────
def load_as_luma(path: str) -> np.ndarray:
    """加载图像并转为灰度，自动 resize 到 TARGET_W×TARGET_H。"""
    img = Image.open(path).convert("L")
    if img.size != (TARGET_W, TARGET_H):
        img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    return np.array(img, dtype=np.uint8)


# ─── 检测1：边缘近邻 ──────────────────────────────────────────────────────
def check_edge_proximity(luma: np.ndarray, margin: int = EDGE_MARGIN) -> dict:
    """检测内容像素是否距四边框过近。"""
    content = luma >= CONTENT_THRESHOLD
    violations = []

    # 四条边方向：(名称, 条带切片, 扫描轴)
    strips = [
        ("top",    content[:margin, :],  "y"),
        ("bottom", content[-margin:, :], "y"),
        ("left",   content[:, :margin],  "x"),
        ("right",  content[:, -margin:], "x"),
    ]

    for name, strip, _ in strips:
        if strip.any():
            # 计算最近内容像素距对应边框的距离
            rows, cols = np.where(strip)
            if name == "top":
                min_dist = int(rows.min())
            elif name == "bottom":
                min_dist = margin - 1 - int(rows.max())
            elif name == "left":
                min_dist = int(cols.min())
            else:  # right
                min_dist = margin - 1 - int(cols.max())
            violations.append({
                "edge": name,
                "min_distance_px": min_dist,
                "message": f"{name}侧边缘有内容距边框仅{min_dist}px，可能被裁切"
            })

    passed = len(violations) == 0
    return {
        "passed": passed,
        "violations": violations
    }


# ─── 检测2：边框裁切 ──────────────────────────────────────────────────────
def check_border_clipping(
    luma: np.ndarray,
    strip_width: int = BORDER_STRIP,
    pixel_limit: int = BORDER_PIXEL_LIMIT
) -> dict:
    """统计四条边框条带内的内容像素总数，超出阈值视为可能被裁切。"""
    content = luma >= CONTENT_THRESHOLD
    violations = []

    strips = {
        "top":    content[:strip_width, :],
        "bottom": content[-strip_width:, :],
        "left":   content[:, :strip_width],
        "right":  content[:, -strip_width:],
    }

    for name, strip in strips.items():
        count = int(strip.sum())
        if count > pixel_limit:
            violations.append({
                "edge": name,
                "pixel_count": count,
                "message": f"{name}侧边框条带内有{count}个内容像素，内容可能被裁切"
            })

    passed = len(violations) == 0
    return {
        "passed": passed,
        "violations": violations
    }


# ─── 检测3：重叠热点 ──────────────────────────────────────────────────────
def check_overlap_hotspots(
    luma: np.ndarray,
    grid_size: int = GRID_SIZE,
    density_thresh: float = DENSITY_THRESHOLD,
    pair_limit: int = ADJACENT_PAIR_LIMIT
) -> dict:
    """
    将图像划分为 grid_size×grid_size 网格，计算各格内容像素密度。
    若相邻热点对数 ≥ pair_limit，疑似存在文字/图形重叠。
    """
    content = luma >= CONTENT_THRESHOLD
    rows_n = TARGET_H // grid_size
    cols_n = TARGET_W // grid_size

    # 构建密度矩阵
    density = np.zeros((rows_n, cols_n), dtype=float)
    for r in range(rows_n):
        for c in range(cols_n):
            cell = content[r*grid_size:(r+1)*grid_size, c*grid_size:(c+1)*grid_size]
            density[r, c] = cell.sum() / (grid_size * grid_size)

    hotspot_mask = density >= density_thresh

    # 统计相邻热点对（4-邻域：上下左右）
    adjacent_pairs = 0
    for r in range(rows_n):
        for c in range(cols_n):
            if hotspot_mask[r, c]:
                # 右邻
                if c + 1 < cols_n and hotspot_mask[r, c + 1]:
                    adjacent_pairs += 1
                # 下邻
                if r + 1 < rows_n and hotspot_mask[r + 1, c]:
                    adjacent_pairs += 1

    hotspot_count = int(hotspot_mask.sum())
    passed = adjacent_pairs < pair_limit

    result = {
        "passed": passed,
        "hotspot_cells": hotspot_count,
        "adjacent_hotspot_pairs": adjacent_pairs,
    }
    if not passed:
        result["message"] = (
            f"检测到{adjacent_pairs}对相邻高密度网格（阈值{pair_limit}），"
            f"疑似存在文字或图形重叠"
        )
    return result


# ─── 主入口 ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="检测 Manim 渲染帧的布局质量（边缘近邻、边框裁切、重叠热点）"
    )
    parser.add_argument("--image", required=True, help="帧图像路径（PNG/JPG）")
    parser.add_argument("--frame-id", type=int, default=0, help="帧编号（用于报告）")
    parser.add_argument(
        "--edge-margin", type=int, default=EDGE_MARGIN,
        help=f"边缘近邻警戒距离，单位px（默认{EDGE_MARGIN}）"
    )
    parser.add_argument(
        "--border-threshold", type=int, default=BORDER_PIXEL_LIMIT,
        help=f"边框条带内容像素数上限（默认{BORDER_PIXEL_LIMIT}）"
    )
    args = parser.parse_args()

    if not Path(args.image).exists():
        print(json.dumps({"error": f"图像文件不存在: {args.image}"}), flush=True)
        sys.exit(1)

    t0 = time.time()

    try:
        luma = load_as_luma(args.image)
    except Exception as e:
        print(json.dumps({"error": f"无法加载图像: {e}"}), flush=True)
        sys.exit(1)

    proximity = check_edge_proximity(luma, margin=args.edge_margin)
    clipping  = check_border_clipping(luma, pixel_limit=args.border_threshold)
    hotspots  = check_overlap_hotspots(luma)

    # 汇总所有问题描述
    issues_found = []
    for v in proximity.get("violations", []):
        issues_found.append(v["message"])
    for v in clipping.get("violations", []):
        issues_found.append(v["message"])
    if not hotspots["passed"] and "message" in hotspots:
        issues_found.append(hotspots["message"])

    overall_passed = proximity["passed"] and clipping["passed"] and hotspots["passed"]
    duration_ms = int((time.time() - t0) * 1000)

    report = {
        "frame_id": args.frame_id,
        "overall_passed": overall_passed,
        "issues_found": issues_found,
        "checks": {
            "edge_proximity":   proximity,
            "border_clipping":  clipping,
            "overlap_hotspots": hotspots,
        },
        "duration_ms": duration_ms,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    sys.exit(0 if overall_passed else 1)


if __name__ == "__main__":
    main()
