#!/usr/bin/env python3
"""
Manim 渲染封装脚本
用法: python render_manim.py <manim_script.py> [--output-dir /tmp/frames] [--quality preview|medium] [--workers 4]
"""

import argparse
import ast
import subprocess
import sys
import os
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


QUALITY_FLAGS = {
    "preview": "-ql",   # 480p15，~3-10s/帧，用于验证
    "medium":  "-qm",   # 720p30，~10-60s/帧，用于最终输出
    "high":    "-qh",   # 1080p60
}


def get_scene_names(script_path: str) -> list[str]:
    """从 Manim 脚本中提取所有 Scene 类名"""
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = r"class\s+(Frame\d+Scene)\s*\("
    names = re.findall(pattern, content)
    # 按帧 ID 排序
    names.sort(key=lambda n: int(re.search(r"Frame(\d+)Scene", n).group(1)))
    return names


def validate_script(script_path: str) -> list[str]:
    """
    渲染前预检，捕获常见错误，避免浪费渲染时间。
    返回问题列表（空列表表示通过）。
    """
    issues = []
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Python 语法检查
    try:
        ast.parse(content)
    except SyntaxError as e:
        issues.append(f"SyntaxError at line {e.lineno}: {e.msg}")
        return issues  # 语法错误后无需继续检查

    # 2. LaTeX 依赖检查（MathTex/Tex 需要本地 LaTeX）
    if re.search(r"\bMathTex\b|\bTex\s*\(", content):
        check = subprocess.run(["latex", "--version"], capture_output=True)
        if check.returncode != 0:
            issues.append(
                "检测到 MathTex/Tex 但 LaTeX 未安装 → 替换为 Text()，或运行: brew install --cask mactex"
            )

    # 3. 常见颜色参数错误：.set_color(color=X) 应为 .set_color(X)
    bad_set_color = re.findall(r"\.set_color\s*\(\s*color\s*=", content)
    if bad_set_color:
        issues.append(
            f"发现 {len(bad_set_color)} 处 .set_color(color=...) → 应为 .set_color(COLOR)"
        )

    # 4. 检查 color 关键字传给不接受的方法（如 Line, Arrow 构造函数）
    # Manim 中 Line(A, B, color=X) 是合法的，但 Line(A, B, stroke_color=X) 可能不是
    # 检查已知不接受 color= 的构造调用（这里只做基础检查）
    bad_stroke = re.findall(r"\bLine\s*\([^)]*stroke_color\s*=", content)
    if bad_stroke:
        issues.append(
            f"发现 {len(bad_stroke)} 处 Line(stroke_color=...) → 应为 Line(..., color=...)"
        )

    return issues


def render_scene(
    script_path: str,
    scene_name: str,
    output_dir: str,
    quality: str = "medium",
    timeout: int = 120,
) -> dict:
    """
    渲染单个 Manim Scene。
    返回: {"success": bool, "output_file": str|None, "error": str|None, "elapsed_sec": float}
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    quality_flag = QUALITY_FLAGS.get(quality, "-qm")
    cmd = [
        "manim",
        script_path,
        scene_name,
        quality_flag,
        "--media_dir", str(output_path),
        "--disable_caching",
    ]

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(script_path).parent),
        )
        elapsed = time.monotonic() - t0

        if result.returncode == 0:
            mp4_files = list(output_path.rglob(f"{scene_name}.mp4"))
            if mp4_files:
                return {"success": True, "output_file": str(mp4_files[0]), "error": None, "elapsed_sec": round(elapsed, 1)}
            else:
                return {"success": False, "output_file": None, "error": f"渲染完成但找不到输出文件: {scene_name}.mp4", "elapsed_sec": round(elapsed, 1)}
        else:
            return {"success": False, "output_file": None, "error": result.stderr[-2000:] if result.stderr else "未知错误", "elapsed_sec": round(elapsed, 1)}

    except subprocess.TimeoutExpired:
        return {"success": False, "output_file": None, "error": f"渲染超时（>{timeout}秒）: {scene_name}", "elapsed_sec": timeout}
    except FileNotFoundError:
        return {"success": False, "output_file": None, "error": "找不到 manim 命令，请先安装: pip install manim", "elapsed_sec": 0}


def render_all(
    script_path: str,
    output_dir: str,
    quality: str = "medium",
    timeout: int = 120,
    workers: int = 1,
) -> dict:
    """
    渲染脚本中的所有 Scene，支持并行。
    workers=1 时串行（兼容旧行为），workers>1 时并行。
    返回: {"frames": [{frame_id, scene_name, success, output_file, error, elapsed_sec}]}
    """
    scene_names = get_scene_names(script_path)
    if not scene_names:
        return {"frames": [], "error": f"在 {script_path} 中未找到任何 FrameXScene 类"}

    effective_workers = min(workers, len(scene_names))
    print(f"[Manim] 共 {len(scene_names)} 帧，quality={quality}，workers={effective_workers}", flush=True)

    def _render_one(scene_name):
        match = re.search(r"Frame(\d+)Scene", scene_name)
        frame_id = int(match.group(1)) if match else -1
        print(f"[Manim] → 渲染帧 {frame_id}: {scene_name} ...", flush=True)
        result = render_scene(script_path, scene_name, output_dir, quality, timeout)
        if result["success"]:
            print(f"[Manim] ✅ 帧 {frame_id} ({result['elapsed_sec']}s): {result['output_file']}", flush=True)
        else:
            print(f"[Manim] ❌ 帧 {frame_id} ({result['elapsed_sec']}s): {result['error']}", flush=True)
        return frame_id, scene_name, result

    results = []

    if effective_workers <= 1:
        for scene_name in scene_names:
            frame_id, scene_name, result = _render_one(scene_name)
            results.append({"frame_id": frame_id, "scene_name": scene_name, **result})
    else:
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            futures = {executor.submit(_render_one, name): name for name in scene_names}
            for future in as_completed(futures):
                frame_id, scene_name, result = future.result()
                results.append({"frame_id": frame_id, "scene_name": scene_name, **result})

    results.sort(key=lambda x: x["frame_id"])
    return {"frames": results}


def main():
    parser = argparse.ArgumentParser(description="Manim 渲染封装")
    parser.add_argument("script", help="Manim Python 脚本路径")
    parser.add_argument("--output-dir", default="/tmp/manim_output", help="输出目录")
    parser.add_argument("--timeout", type=int, default=120, help="单帧渲染超时秒数")
    parser.add_argument("--scene", help="只渲染指定场景名（可选）")
    parser.add_argument(
        "--quality",
        choices=["preview", "medium", "high"],
        default="medium",
        help="渲染质量: preview(480p,快速验证) | medium(720p,默认) | high(1080p)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="并行渲染 worker 数量（默认 4，设为 1 可串行调试）",
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="跳过渲染前预检（不推荐）",
    )
    args = parser.parse_args()

    if not os.path.exists(args.script):
        print(f"错误：脚本文件不存在: {args.script}", file=sys.stderr)
        sys.exit(1)

    # 预检
    if not args.skip_validate and not args.scene:
        print("[Validate] 预检脚本...", flush=True)
        issues = validate_script(args.script)
        if issues:
            print("[Validate] ⚠️  发现以下问题，请修复后再渲染：", flush=True)
            for issue in issues:
                print(f"  • {issue}", flush=True)
            sys.exit(2)
        print("[Validate] ✅ 预检通过", flush=True)

    if args.scene:
        result = render_scene(args.script, args.scene, args.output_dir, args.quality, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        t0 = time.monotonic()
        result = render_all(args.script, args.output_dir, args.quality, args.timeout, args.workers)
        total_elapsed = time.monotonic() - t0

        frames = result.get("frames", [])
        success_count = sum(1 for f in frames if f["success"])
        print(f"\n[Manim] 完成: {success_count}/{len(frames)} 帧成功，总耗时 {total_elapsed:.0f}s", flush=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
