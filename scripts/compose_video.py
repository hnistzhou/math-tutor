#!/usr/bin/env python3
"""
FFmpeg 音视频合成脚本
将所有分镜帧的视频/静态图 + 音频按顺序合成为最终 MP4。

用法:
  python compose_video.py \
    --storyboard /tmp/storyboard.json \
    --frames-dir /tmp/manim_output \
    --audio-dir /tmp/audio \
    --source-image original_problem.png \
    --output ./output.mp4 \
    --quality 720p
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def create_static_frame_video(
    image_path: str,
    duration_sec: float,
    output_path: str,
) -> dict:
    """将静态图片转为指定时长的视频（用于降级帧）"""
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-t", str(duration_sec),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-r", "25",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0:
            return {"success": True, "output_file": output_path, "error": None}
        stderr = result.stderr.decode("utf-8", errors="replace")[-500:]
        return {"success": False, "output_file": None, "error": stderr}
    except subprocess.TimeoutExpired:
        return {"success": False, "output_file": None, "error": "静态帧转视频超时"}


def get_video_duration(video_path: str) -> float:
    """用 ffprobe 获取视频时长（秒），失败返回 0.0"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0:
            return float(result.stdout.decode().strip())
    except Exception:
        pass
    return 0.0


def mux_video_audio(
    video_path: str,
    audio_path: str | None,
    duration_ms: int,
    output_path: str,
) -> dict:
    """
    将视频与音频合并，冻结视频最后一帧直到音频结束（不循环播放）。
    如果无音频，冻结最后帧至 duration_sec。
    """
    duration_sec = max(duration_ms / 1000, 0.5) if duration_ms > 0 else 3.0

    video_duration = get_video_duration(video_path)
    extra_sec = max(0.0, duration_sec - video_duration + 1.0)

    if audio_path and os.path.exists(audio_path):
        # tpad 冻结最后一帧，-shortest 在音频结束时截断
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={extra_sec:.2f}[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_path,
        ]
    else:
        # 无声视频，冻结最后帧至 duration_sec
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={extra_sec:.2f}[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-t", str(duration_sec),
            "-an",
            output_path,
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            return {"success": True, "output_file": output_path, "error": None}
        stderr = result.stderr.decode("utf-8", errors="replace")[-500:]
        return {"success": False, "output_file": None, "error": stderr}
    except subprocess.TimeoutExpired:
        return {"success": False, "output_file": None, "error": "音视频合并超时"}


def concatenate_videos(video_files: list[str], output_path: str) -> dict:
    """用 FFmpeg concat demuxer 拼接多段视频"""
    if not video_files:
        return {"success": False, "output_file": None, "error": "没有视频文件可拼接"}

    if len(video_files) == 1:
        # 只有一段，直接复制
        import shutil
        shutil.copy2(video_files[0], output_path)
        return {"success": True, "output_file": output_path, "error": None}

    # 创建 concat 列表文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for vf in video_files:
            # FFmpeg concat 格式要求绝对路径
            abs_path = os.path.abspath(vf)
            f.write(f"file '{abs_path}'\n")
        concat_file = f.name

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        os.unlink(concat_file)

        if result.returncode == 0:
            return {"success": True, "output_file": output_path, "error": None}
        stderr = result.stderr.decode("utf-8", errors="replace")[-1000:]
        return {"success": False, "output_file": None, "error": stderr}

    except subprocess.TimeoutExpired:
        if os.path.exists(concat_file):
            os.unlink(concat_file)
        return {"success": False, "output_file": None, "error": "视频拼接超时（>300秒）"}
    except FileNotFoundError:
        return {"success": False, "output_file": None, "error": "找不到 ffmpeg，请先安装 FFmpeg"}


def compose(
    storyboard: dict,
    frames_dir: str,
    audio_dir: str,
    source_image: str | None,
    output_path: str,
) -> dict:
    """
    主合成流程。
    返回: {"success": bool, "output_file": str, "stats": {...}, "error": str|None}
    """
    frames = storyboard.get("frames", [])
    if not frames:
        return {"success": False, "output_file": None, "error": "分镜为空"}

    with tempfile.TemporaryDirectory() as tmpdir:
        segment_videos = []
        stats = {
            "total_frames": len(frames),
            "fallback_frames": 0,
            "no_audio_frames": 0,
            "total_duration_sec": 0,
        }

        for frame in frames:
            frame_id = frame["id"]
            is_fallback = frame.get("fallback", False)
            duration_hint_sec = frame.get("duration_hint_sec", 10)
            duration_ms = frame.get("audio_duration_ms", duration_hint_sec * 1000)

            print(f"[Compose] 处理帧 {frame_id}...", flush=True)

            # 1. 确定视频来源
            if is_fallback or True:  # 先尝试 Manim 输出
                manim_video = os.path.join(frames_dir, f"Frame{frame_id}Scene.mp4")
                # 搜索可能的路径（Manim 输出目录结构可能嵌套）
                if not os.path.exists(manim_video):
                    candidates = list(Path(frames_dir).rglob(f"Frame{frame_id}Scene.mp4"))
                    manim_video = str(candidates[0]) if candidates else None

            use_static = is_fallback or not manim_video or not os.path.exists(manim_video or "")

            frame_video_path = os.path.join(tmpdir, f"frame_{frame_id:03d}_raw.mp4")

            if use_static:
                # 降级：使用静态图
                stats["fallback_frames"] += 1
                fallback_image = source_image
                if not fallback_image or not os.path.exists(fallback_image):
                    # 生成纯色占位图
                    placeholder = os.path.join(tmpdir, "placeholder.png")
                    subprocess.run([
                        "ffmpeg", "-y",
                        "-f", "lavfi", "-i", f"color=c=0x1a1a2e:s=1280x720:r=25",
                        "-vframes", "1",
                        placeholder,
                    ], capture_output=True, timeout=10)
                    fallback_image = placeholder

                result = create_static_frame_video(
                    fallback_image,
                    duration_ms / 1000,
                    frame_video_path,
                )
                if not result["success"]:
                    print(f"[Compose] ❌ 帧 {frame_id} 静态图转视频失败: {result['error']}", flush=True)
                    continue
            else:
                frame_video_path = manim_video  # type: ignore

            # 2. 确定音频来源
            audio_path = os.path.join(audio_dir, f"audio_frame_{frame_id}.mp3")
            if not os.path.exists(audio_path):
                audio_path = None
                stats["no_audio_frames"] += 1

            # 3. 音视频合并
            mux_output = os.path.join(tmpdir, f"segment_{frame_id:03d}.mp4")
            mux_result = mux_video_audio(frame_video_path, audio_path, duration_ms, mux_output)

            if mux_result["success"]:
                segment_videos.append(mux_output)
                stats["total_duration_sec"] += duration_ms / 1000
                print(f"[Compose] ✅ 帧 {frame_id} 处理完成", flush=True)
            else:
                print(f"[Compose] ❌ 帧 {frame_id} 音视频合并失败: {mux_result['error']}", flush=True)

        if not segment_videos:
            return {
                "success": False,
                "output_file": None,
                "stats": stats,
                "error": "所有帧处理失败，无法合成视频",
            }

        # 4. 拼接所有分段
        print(f"[Compose] 拼接 {len(segment_videos)} 段视频...", flush=True)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        concat_result = concatenate_videos(segment_videos, output_path)

        if concat_result["success"]:
            file_size_mb = os.path.getsize(output_path) / 1024 / 1024
            print(f"[Compose] ✅ 合成完成: {output_path} ({file_size_mb:.1f} MB)", flush=True)
            return {
                "success": True,
                "output_file": output_path,
                "stats": {**stats, "file_size_mb": file_size_mb},
                "error": None,
            }
        else:
            return {
                "success": False,
                "output_file": None,
                "stats": stats,
                "error": concat_result["error"],
            }


def main():
    parser = argparse.ArgumentParser(description="FFmpeg 音视频合成")
    parser.add_argument("--storyboard", required=True, help="分镜 JSON 文件路径")
    parser.add_argument("--frames-dir", required=True, help="Manim 渲染输出目录")
    parser.add_argument("--audio-dir", required=True, help="音频文件目录")
    parser.add_argument("--source-image", help="原始题目图片（用于降级帧）")
    parser.add_argument("--output", required=True, help="输出 MP4 路径")
    parser.add_argument("--quality", default="720p", help="输出质量（目前仅支持 720p）")
    args = parser.parse_args()

    if not os.path.exists(args.storyboard):
        print(f"错误：分镜文件不存在: {args.storyboard}", file=sys.stderr)
        sys.exit(1)

    with open(args.storyboard, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    result = compose(
        storyboard=storyboard,
        frames_dir=args.frames_dir,
        audio_dir=args.audio_dir,
        source_image=args.source_image,
        output_path=args.output,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
