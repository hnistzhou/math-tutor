#!/usr/bin/env python3
"""
关键帧提取脚本 - 供 Claude Vision 验证使用
用法: python extract_frames.py --video input.mp4 --output keyframe.png [--timestamp middle|start|end|<秒数>]
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_video_duration(video_path: str) -> float:
    """用 ffprobe 获取视频时长（秒）"""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
    except Exception:
        pass
    return -1.0


def resolve_timestamp(timestamp_spec: str, duration: float) -> float:
    """
    解析时间戳规格：
    - "middle": 视频中间
    - "start": 0.5秒处
    - "end": 倒数0.5秒
    - "25%", "75%": 百分比位置
    - 数字字符串: 直接作为秒数
    """
    if timestamp_spec == "middle":
        return duration / 2 if duration > 0 else 0.5
    elif timestamp_spec == "start":
        return min(0.5, duration * 0.1) if duration > 0 else 0.5
    elif timestamp_spec == "end":
        return max(0, duration - 0.5) if duration > 0 else 0.5
    elif timestamp_spec.endswith("%"):
        pct = float(timestamp_spec[:-1]) / 100
        return duration * pct if duration > 0 else 0.5
    else:
        return float(timestamp_spec)


def extract_frame(
    video_path: str,
    output_path: str,
    timestamp_spec: str = "middle",
    use_cache: bool = True,
) -> dict:
    """
    从视频中提取关键帧。
    use_cache=True 时：若 output_path 已存在且比 video_path 更新，直接返回缓存结果，跳过 FFmpeg。
    返回: {"success": bool, "output_file": str|None, "timestamp_sec": float, "error": str|None}
    """
    if not os.path.exists(video_path):
        return {
            "success": False,
            "output_file": None,
            "timestamp_sec": -1,
            "error": f"视频文件不存在: {video_path}",
        }

    # 缓存检查：若已提取过且视频未更新，直接返回缓存
    if use_cache and os.path.exists(output_path):
        cache_mtime = os.path.getmtime(output_path)
        video_mtime = os.path.getmtime(video_path)
        cache_size = os.path.getsize(output_path)
        if cache_mtime >= video_mtime and cache_size >= 100:
            return {
                "success": True,
                "output_file": output_path,
                "timestamp_sec": -1,  # 缓存命中，无需重新计算时间戳
                "file_size_bytes": cache_size,
                "error": None,
                "from_cache": True,
            }

    duration = get_video_duration(video_path)
    timestamp_sec = resolve_timestamp(timestamp_spec, duration)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp_sec),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",        # 高质量截图
        "-vf", "scale=1280:720",   # 统一 720p 分辨率
        output_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=15,
        )

        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size < 100:  # 空文件或极小文件
                return {
                    "success": False,
                    "output_file": None,
                    "timestamp_sec": timestamp_sec,
                    "error": f"提取的帧文件异常（{file_size} bytes）",
                }
            return {
                "success": True,
                "output_file": output_path,
                "timestamp_sec": timestamp_sec,
                "file_size_bytes": file_size,
                "error": None,
            }
        else:
            stderr = result.stderr.decode("utf-8", errors="replace")[-1000:]
            return {
                "success": False,
                "output_file": None,
                "timestamp_sec": timestamp_sec,
                "error": f"ffmpeg 失败: {stderr}",
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output_file": None,
            "timestamp_sec": timestamp_sec,
            "error": "ffmpeg 超时",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "output_file": None,
            "timestamp_sec": timestamp_sec,
            "error": "找不到 ffmpeg 命令，请先安装 FFmpeg",
        }


def extract_multiple(
    video_path: str,
    output_dir: str,
    count: int = 3,
) -> dict:
    """
    从视频中均匀提取多帧（用于更全面的视觉验证）。
    返回: {"frames": [{output_file, timestamp_sec, success}]}
    """
    duration = get_video_duration(video_path)
    if duration <= 0:
        return {"frames": [], "error": "无法获取视频时长"}

    frames = []
    step = duration / (count + 1)

    for i in range(1, count + 1):
        ts = step * i
        output_path = os.path.join(output_dir, f"frame_{i:03d}.png")
        result = extract_frame(video_path, output_path, str(ts))
        frames.append({
            "index": i,
            "output_file": result.get("output_file"),
            "timestamp_sec": result.get("timestamp_sec", ts),
            "success": result["success"],
            "error": result.get("error"),
        })

    return {"frames": frames}


def main():
    parser = argparse.ArgumentParser(description="从视频提取关键帧供 Vision 验证")
    parser.add_argument("--video", required=True, help="输入视频路径")
    parser.add_argument("--output", help="输出图片路径（单帧模式）")
    parser.add_argument("--output-dir", help="输出目录（多帧模式）")
    parser.add_argument(
        "--timestamp",
        default="middle",
        help="时间戳: middle|start|end|<秒数>|<百分比%>",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=3,
        help="多帧模式提取帧数（与 --output-dir 配合使用）",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="禁用缓存，强制重新提取（视频重新渲染后使用此选项）",
    )
    args = parser.parse_args()

    if args.output_dir:
        result = extract_multiple(args.video, args.output_dir, args.count)
    elif args.output:
        result = extract_frame(args.video, args.output, args.timestamp, use_cache=not args.no_cache)
    else:
        print("错误：必须指定 --output 或 --output-dir", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("success", len(result.get("frames", [])) > 0) else 1)


if __name__ == "__main__":
    main()
