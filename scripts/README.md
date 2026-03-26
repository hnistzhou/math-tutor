# Scripts Reference

Pipeline 脚本参考。每个脚本支持 `--help` 查看完整参数。

## render_manim.py

渲染 Manim 动画。

```bash
# 预览模式 (480p15fps, ~3-10s/frame) - 用于 Stage 4 验证
python scripts/render_manim.py /tmp/animation.py --quality preview

# 正式模式 (720p30fps, ~10-60s/frame) - 验证通过后使用
python scripts/render_manim.py /tmp/animation.py --quality medium
```

**参数**: `--quality preview|medium`, `--output-dir`

---

## synthesize_voice.py

语音合成（CosyVoice 2 或系统 TTS 降级）。

```bash
python scripts/synthesize_voice.py \
  --text "旁白文字" \
  --frame-id 1 \
  --output /tmp/audio_frame_1.mp3 \
  --style "温和清晰，语速偏慢"
```

**参数**: `--text`, `--frame-id`, `--output`, `--style`

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
