# Scripts Reference

Pipeline 脚本参考。每个脚本支持 `--help` 查看完整参数。

## render_manim.py

渲染 Manim 动画，支持并行渲染和渲染前预检。

```bash
# 预览模式 + 4 路并行（用于 Stage 4 验证，典型耗时 ~1-2min）
python scripts/render_manim.py /tmp/animation.py --quality preview --workers 4

# 正式模式（验证通过后）
python scripts/render_manim.py /tmp/animation.py --quality medium --workers 4

# 只渲染指定帧（修复单帧时使用）
python scripts/render_manim.py /tmp/animation.py --scene Frame3Scene --quality preview
```

**参数**:
- `--quality preview|medium|high`：渲染质量，preview=480p（默认 medium=720p）
- `--workers N`：并行 worker 数，默认 4（9 帧约节省 75% 时间）
- `--skip-validate`：跳过渲染前代码预检
- `--scene NAME`：只渲染指定场景

---

## synthesize_voice.py

语音合成（CosyVoice 2 或系统 TTS 降级），支持批量并行合成。

```bash
# 单帧
python scripts/synthesize_voice.py \
  --text "旁白文字" \
  --frame-id 1 \
  --output /tmp/audio_frame_1.mp3

# 批量并行（推荐，9 帧同时合成）
# 先生成 batch JSON，再批量调用
python scripts/synthesize_voice.py --batch-file /tmp/tts_batch.json --workers 4
```

批量 JSON 格式：
```json
[
  {"frame_id": 1, "text": "旁白1", "output": "/tmp/audio_1.mp3"},
  {"frame_id": 2, "text": "旁白2", "output": "/tmp/audio_2.mp3"}
]
```

**参数**: `--text/--frame-id/--output`（单帧）或 `--batch-file`（批量）、`--workers N`

---

## extract_frames.py

从视频中提取关键帧用于 Vision 验证。

```bash
python scripts/extract_frames.py \
  --video /tmp/frame.mp4 \
  --output /tmp/keyframe.png \
  --timestamp middle
```

**参数**:
- `--video`: 输入视频路径
- `--output`: 输出图片路径
- `--timestamp`: `start|middle|end` 或具体时间戳
- `--no-cache`: 修复后重新渲染时必须使用，强制刷新缓存

---

## compose_video.py

合成最终视频。

```bash
python scripts/compose_video.py \
  --storyboard /tmp/storyboard.json \
  --output ./output.mp4 \
  --quality 720p
```

**参数**: `--storyboard`, `--output`, `--quality`, `--frames-dir`, `--audio-dir`, `--source-image`

---

## check_layout.py

程序化布局预检（Stage 4.1.5）。

```bash
python scripts/check_layout.py \
  --image /tmp/keyframe.png \
  --frame-id 1
```

**参数**: `--image`, `--frame-id`

**返回**: JSON 格式的布局检查结果
