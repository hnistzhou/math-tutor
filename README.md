# Math Tutor Skill

> 为5年级学生家长构建的 Claude Code Skill：将数学错题图片转化为2-3分钟教学视频，帮助孩子理解"为什么做错"。

## 功能

- 自动识别数学题型（几何、计算、分数、应用题等）
- 生成分镜式讲解脚本（含视觉动画意图）
- 用 Manim 渲染数学动画，Claude Vision 验证正确性
- CosyVoice 2 合成自然中文讲解语音
- FFmpeg 合成最终教学视频（720p，2-3分钟）
- 优雅降级：任何环节失败均有备用方案

## 环境要求

- **Python 3.10+**
- **FFmpeg**（系统级安装）
- **Manim Community Edition**
- **CosyVoice 2**（本地 TTS 服务，可选）

## 快速安装

### 1. 系统依赖

**macOS**:
```bash
brew install ffmpeg
```

**Ubuntu/Debian**:
```bash
sudo apt-get install ffmpeg libcairo2-dev libpango1.0-dev
```

### 2. Python 依赖

```bash
pip install -r requirements.txt
```

### 3. Manim 验证

```bash
manim --version
# 应输出: Manim Community v0.18.x
```

### 4. CosyVoice 2（可选，推荐）

CosyVoice 2 提供高质量中文语音合成。如不安装，将自动降级到系统 TTS。

**方式一：Docker（推荐）**
```bash
# 拉取官方镜像（如有）
docker run -d -p 50000:50000 cosyvoice2:latest

# 或使用社区镜像
docker run -d -p 50000:50000 your-cosyvoice-image
```

**方式二：本地安装**
```bash
git clone https://github.com/FunAudioLLM/CosyVoice
cd CosyVoice
pip install -r requirements.txt
# 下载模型权重（见官方文档）
python api.py --port 50000
```

**环境变量配置**:
```bash
export COSYVOICE_HOST=localhost
export COSYVOICE_PORT=50000
export COSYVOICE_SPEAKER=中文女声
```

## 使用方法

### 在 Claude Code 中使用

1. 将本 Skill 添加到 Claude Code：
   ```
   /add-skill /path/to/math-tutor/SKILL.md
   ```

2. 发送数学错题图片并说明情况：
   ```
   [附上题目图片]
   孩子做三角形面积题时忘记除以2，请帮我生成一个讲解视频
   ```

3. Claude 将自动执行完整 Pipeline，最终输出 `output_<时间戳>.mp4`

### 脚本单独使用

详见 [scripts/README.md](scripts/README.md)

## Pipeline 说明

```
题目图片
    ↓
Stage 1: Claude Vision 理解题目
    ↓
Stage 2: 生成分镜脚本（自动验证）
    ↓
Stage 3A: Manim 动画渲染    ←→  Stage 3B: CosyVoice 语音合成
    ↓
Stage 4: Vision 验证 + 修复循环（≤3次）
    ↓
Stage 5: FFmpeg 合成 output.mp4
```

## 降级策略

| 场景 | 降级方案 |
|------|---------|
| CosyVoice 不可用 | macOS say 命令（中文 Ting-Ting 声音） |
| say 也不可用 | 输出无声视频 |
| Manim 渲染失败（3次） | 使用原始题目图片作为静态帧 |
| 所有帧均降级 | 输出"题目静态图 + 语音讲解"视频 |

## 验证安装

```bash
# 语音合成测试
python scripts/synthesize_voice.py --text "3加5等于8" --frame-id 0 --output /tmp/test.mp3

# 帧提取测试
python scripts/extract_frames.py --video /any/video.mp4 --output /tmp/test.png
```

详细脚本用法见 [scripts/README.md](scripts/README.md)。

## 已知限制

- Manim 渲染速度较慢（单帧 10-60 秒），完整视频生成约 5-15 分钟
- CosyVoice 2 模型文件较大（约 2-4 GB），首次启动需下载
- 极复杂的几何图（多个辅助线交叉）可能需要多次修复
- 当前不支持英文题目（可扩展）

## 开放问题

- [ ] CosyVoice 2 最佳本地部署方案（Docker vs 裸机）
- [ ] Manim 渲染超时阈值（当前默认 60 秒/帧）
- [ ] 输出视频存储位置配置化
- [ ] 批量处理多道错题的支持

## 许可

本 Skill 仅供个人教育用途。
