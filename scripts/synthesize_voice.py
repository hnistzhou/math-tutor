#!/usr/bin/env python3
"""
CosyVoice 2 语音合成封装脚本
用法: python synthesize_voice.py --text "文本" --frame-id 1 --output /tmp/audio_1.mp3

依赖 CosyVoice 2 本地服务（默认端口 50000）或 HTTP API。
如果 CosyVoice 不可用，会自动降级到系统 TTS（macOS say 命令）。
"""

import argparse
import json
import os
import sys
import subprocess
import tempfile
import time
from pathlib import Path


# CosyVoice 2 服务配置
COSYVOICE_HOST = os.getenv("COSYVOICE_HOST", "localhost")
COSYVOICE_PORT = int(os.getenv("COSYVOICE_PORT", "50000"))
COSYVOICE_SPEAKER = os.getenv("COSYVOICE_SPEAKER", "中文女声")  # 温和清晰风格


def get_audio_duration_ms(audio_path: str) -> int:
    """用 ffprobe 获取音频时长（毫秒）"""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration_sec = float(data["format"]["duration"])
            return int(duration_sec * 1000)
    except Exception:
        pass

    # 降级：估算（每字约200ms，中文语速偏慢）
    # 这个估算只在 ffprobe 失败时使用
    return -1


def synthesize_cosyvoice(text: str, output_path: str, style: str = "") -> dict:
    """
    调用 CosyVoice 2 HTTP API 合成语音。
    返回: {"success": bool, "duration_ms": int, "error": str|None}
    """
    try:
        import urllib.request
        import urllib.parse

        url = f"http://{COSYVOICE_HOST}:{COSYVOICE_PORT}/inference_sft"
        data = {
            "tts_text": text,
            "spk_id": COSYVOICE_SPEAKER,
            "speed": 0.85,  # 语速偏慢，适合学生
        }

        req_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            audio_data = response.read()

        # 写入临时 WAV 文件再转 MP3
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_wav = tmp.name

        # 转换为 MP3
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_wav, "-q:a", "4", output_path],
            capture_output=True,
            timeout=30,
        )
        os.unlink(tmp_wav)

        if result.returncode != 0:
            return {"success": False, "duration_ms": -1, "error": "MP3 转换失败"}

        duration_ms = get_audio_duration_ms(output_path)
        return {"success": True, "duration_ms": duration_ms, "error": None}

    except ConnectionRefusedError:
        return {
            "success": False,
            "duration_ms": -1,
            "error": f"CosyVoice 服务未启动（{COSYVOICE_HOST}:{COSYVOICE_PORT}）",
        }
    except Exception as e:
        return {"success": False, "duration_ms": -1, "error": str(e)}


def synthesize_edge_tts(text: str, output_path: str) -> dict:
    """
    Tier-2 降级：使用 edge-tts（微软 Azure Neural TTS 免费端点）合成语音。
    声音：zh-CN-XiaoxiaoNeural（晓晓，温和亲切，适合教学）
    """
    try:
        import asyncio
        import edge_tts

        async def _run():
            communicate = edge_tts.Communicate(
                text,
                voice="zh-CN-XiaoxiaoNeural",
                rate="-4%",   # 轻微减速，适合小学生
            )
            await communicate.save(output_path)

        asyncio.run(_run())

        duration_ms = get_audio_duration_ms(output_path)
        return {"success": True, "duration_ms": duration_ms, "error": None}

    except ImportError:
        return {"success": False, "duration_ms": -1, "error": "edge-tts 未安装，运行 pip install edge-tts"}
    except Exception as e:
        return {"success": False, "duration_ms": -1, "error": str(e)}


def synthesize_macos_say(text: str, output_path: str) -> dict:
    """
    Tier-3 降级：使用 macOS say 命令合成语音。
    只在 CosyVoice 和 edge-tts 都不可用时使用。
    """
    try:
        aiff_path = output_path.replace(".mp3", ".aiff")
        # 尝试 Enhanced（macOS 14+），降级到 Ting-Ting
        result = None
        for voice in ["Tingting (Enhanced)", "Ting-Ting"]:
            result = subprocess.run(
                ["say", "-v", voice, "-r", "150", "-o", aiff_path, text],
                capture_output=True,
                timeout=60,
            )
            if result.returncode == 0:
                break

        if result is None or result.returncode != 0:
            return {"success": False, "duration_ms": -1, "error": "say 命令失败"}

        # 转 MP3
        conv_result = subprocess.run(
            ["ffmpeg", "-y", "-i", aiff_path, "-q:a", "4", output_path],
            capture_output=True,
            timeout=30,
        )

        if os.path.exists(aiff_path):
            os.unlink(aiff_path)

        if conv_result.returncode != 0:
            return {"success": False, "duration_ms": -1, "error": "AIFF→MP3 转换失败"}

        duration_ms = get_audio_duration_ms(output_path)
        return {"success": True, "duration_ms": duration_ms, "error": None, "fallback": "macos_say"}

    except FileNotFoundError:
        return {"success": False, "duration_ms": -1, "error": "say 命令不存在（非 macOS 环境）"}
    except Exception as e:
        return {"success": False, "duration_ms": -1, "error": str(e)}


def estimate_duration_ms(text: str) -> int:
    """
    基于字数估算音频时长（降级使用）。
    中文语速约 200 字/分钟（偏慢教学风格）。
    """
    char_count = len(text.replace(" ", "").replace("\n", ""))
    chars_per_second = 200 / 60  # ≈3.33 字/秒
    return int(char_count / chars_per_second * 1000)


def synthesize(text: str, frame_id: int, output_path: str, style: str = "") -> dict:
    """
    主合成入口，自动降级。
    返回: {"success": bool, "duration_ms": int, "output_file": str, "method": str, "error": str|None}
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 尝试 CosyVoice 2
    print(f"[TTS] 帧 {frame_id}: 尝试 CosyVoice 2...", flush=True)
    result = synthesize_cosyvoice(text, output_path, style)

    if result["success"]:
        print(f"[TTS] ✅ 帧 {frame_id}: CosyVoice 合成成功，时长 {result['duration_ms']}ms", flush=True)
        return {**result, "output_file": output_path, "method": "cosyvoice2"}

    # Tier-2: edge-tts
    print(f"[TTS] ⚠️  CosyVoice 失败: {result['error']}，降级到 edge-tts...", flush=True)
    result = synthesize_edge_tts(text, output_path)
    if result["success"]:
        print(f"[TTS] ✅ 帧 {frame_id}: edge-tts 合成成功，时长 {result['duration_ms']}ms", flush=True)
        return {**result, "output_file": output_path, "method": "edge_tts"}

    # Tier-3: macOS say
    print(f"[TTS] ⚠️  edge-tts 失败: {result['error']}，降级到 macOS say...", flush=True)
    result = synthesize_macos_say(text, output_path)
    if result["success"]:
        print(f"[TTS] ✅ 帧 {frame_id}: macOS say 合成成功，时长 {result['duration_ms']}ms", flush=True)
        return {**result, "output_file": output_path, "method": "macos_say"}

    # 完全失败：估算时长，标记为无音频
    estimated_ms = estimate_duration_ms(text)
    print(f"[TTS] ❌ 帧 {frame_id}: 语音合成完全失败，估算时长 {estimated_ms}ms", flush=True)
    return {
        "success": False,
        "duration_ms": estimated_ms,
        "output_file": None,
        "method": "none",
        "error": result["error"],
    }


def main():
    parser = argparse.ArgumentParser(description="CosyVoice 2 语音合成封装")
    parser.add_argument("--text", required=True, help="要合成的文本")
    parser.add_argument("--frame-id", type=int, required=True, help="帧 ID")
    parser.add_argument("--output", required=True, help="输出 MP3 文件路径")
    parser.add_argument("--style", default="温和清晰，语速偏慢，适合小学生", help="语音风格描述")
    args = parser.parse_args()

    result = synthesize(args.text, args.frame_id, args.output, args.style)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
