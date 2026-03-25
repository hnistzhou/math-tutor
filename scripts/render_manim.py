#!/usr/bin/env python3
"""
Manim 渲染封装脚本
用法: python render_manim.py <manim_script.py> [--output-dir /tmp/frames]
"""

import argparse
import subprocess
import sys
import os
import json
import re
import time
from pathlib import Path


def get_scene_names(script_path: str) -> list[str]:
    """从 Manim 脚本中提取所有 Scene 类名"""
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
    # 匹配 class FrameXScene(Scene): 模式
    pattern = r"class\s+(Frame\d+Scene)\s*\("
    return re.findall(pattern, content)


def render_scene(
    script_path: str,
    scene_name: str,
    output_dir: str,
    timeout: int = 60,
) -> dict:
    """
    渲染单个 Manim Scene。
    返回: {"success": bool, "output_file": str|None, "error": str|None}
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        "manim",
        script_path,
        scene_name,
        "-qm",           # medium quality = 720p30，速度优先
        "--media_dir", str(output_path),
        "--disable_caching",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(script_path).parent),
        )

        if result.returncode == 0:
            # Manim 输出文件路径通常在 media/videos/<scene>/<quality>/
            # 搜索实际生成的文件
            mp4_files = list(output_path.rglob(f"{scene_name}.mp4"))
            if mp4_files:
                return {"success": True, "output_file": str(mp4_files[0]), "error": None}
            else:
                return {
                    "success": False,
                    "output_file": None,
                    "error": f"渲染完成但找不到输出文件: {scene_name}.mp4",
                }
        else:
            return {
                "success": False,
                "output_file": None,
                "error": result.stderr[-2000:] if result.stderr else "未知错误",
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output_file": None,
            "error": f"渲染超时（>{timeout}秒）: {scene_name}",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "output_file": None,
            "error": "找不到 manim 命令，请先安装: pip install manim",
        }


def render_all(script_path: str, output_dir: str, timeout: int = 60) -> dict:
    """
    渲染脚本中的所有 Scene。
    返回: {"frames": [{frame_id, scene_name, success, output_file, error}]}
    """
    scene_names = get_scene_names(script_path)
    if not scene_names:
        return {
            "frames": [],
            "error": f"在 {script_path} 中未找到任何 FrameXScene 类",
        }

    results = []
    for scene_name in scene_names:
        # 从 FrameXScene 提取帧 ID
        match = re.search(r"Frame(\d+)Scene", scene_name)
        frame_id = int(match.group(1)) if match else -1

        print(f"[Manim] 渲染帧 {frame_id}: {scene_name} ...", flush=True)
        result = render_scene(script_path, scene_name, output_dir, timeout)

        results.append({
            "frame_id": frame_id,
            "scene_name": scene_name,
            "success": result["success"],
            "output_file": result["output_file"],
            "error": result["error"],
        })

        if result["success"]:
            print(f"[Manim] ✅ 帧 {frame_id} 渲染成功: {result['output_file']}", flush=True)
        else:
            print(f"[Manim] ❌ 帧 {frame_id} 渲染失败: {result['error']}", flush=True)

    return {"frames": results}


def main():
    parser = argparse.ArgumentParser(description="Manim 渲染封装")
    parser.add_argument("script", help="Manim Python 脚本路径")
    parser.add_argument("--output-dir", default="/tmp/manim_output", help="输出目录")
    parser.add_argument("--timeout", type=int, default=60, help="单帧渲染超时秒数")
    parser.add_argument("--scene", help="只渲染指定场景名（可选）")
    args = parser.parse_args()

    if not os.path.exists(args.script):
        print(f"错误：脚本文件不存在: {args.script}", file=sys.stderr)
        sys.exit(1)

    if args.scene:
        result = render_scene(args.script, args.scene, args.output_dir, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = render_all(args.script, args.output_dir, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))

        # 统计成功率
        frames = result.get("frames", [])
        success_count = sum(1 for f in frames if f["success"])
        print(f"\n[Manim] 完成: {success_count}/{len(frames)} 帧渲染成功", flush=True)


if __name__ == "__main__":
    main()
