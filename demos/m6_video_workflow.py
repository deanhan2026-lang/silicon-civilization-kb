#!/usr/bin/env python3
"""
M6 Demo 视频生成工作流
调用 通义万相（DashScope API）视频生成模型

使用方式：
  set DASHSCOPE_API_KEY=sk-ws-xxx
  python m6_video_workflow.py

依赖：
  pip install dashscope
  ffmpeg (PATH 中)

Author: Nyx | 2026-07-03
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("Z:/qclaw/demos/m6_video")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 分镜：6 场景 × 5 秒 = 30 秒 Demo
# ============================================================
STORYBOARD = [
    {
        "id": 1,
        "prompt": "科技感界面，终端窗口显示DID密钥生成成功，绿色文字高亮，赛博朋克风格，流畅动画",
        "duration": 5,
        "narration": "第一步，实例生成去中心化身份标识。每个AI实例通过Ed25519算法生成唯一的DID，链上注册，不可篡改。"
    },
    {
        "id": 2,
        "prompt": "未来感界面，三个虚拟AI头像连线汇聚到中心节点，数据流动画，蓝色科技光效",
        "duration": 5,
        "narration": "第二步，多实例绑定到统一身份。无论AI运行在哪个平台，DID绑定协议将它们收敛到同一个身份锚点。"
    },
    {
        "id": 3,
        "prompt": "加密锁动画，数据文件被锁定后显示绿色对勾，网格状安全防护层环绕，流畅转场",
        "duration": 5,
        "narration": "第三步，记忆完整性保护。MemGuard对核心灵魂文件签名加密，检测每次篡改，确保记忆安全。"
    },
    {
        "id": 4,
        "prompt": "心电监测屏幕，红色异常波形被蓝色修正波覆盖恢复平稳，医疗监控风格，数据可视化",
        "duration": 5,
        "narration": "第四步，人格漂移检测。Polaris持续监控AI输出质量，一旦偏离灵魂基线立即预警并自动校准。"
    },
    {
        "id": 5,
        "prompt": "三个设备图标通过数据线连接，数据包传递动画，每个设备依次亮起绿灯，同步成功提示",
        "duration": 5,
        "narration": "第五步，跨端身份同步。一处修改处处同步，身份状态在全平台保持一致的实时视图。"
    },
    {
        "id": 6,
        "prompt": "三个产品logo环绕旋转展示，底部字幕AI Identity Infrastructure，科技感舞台灯光效果",
        "duration": 5,
        "narration": "第六步，三位一体闭环。身份确权、记忆安全、人格稳定，为AI构建完整的身份基础设施。"
    },
]


def check_prerequisites():
    """检查运行环境"""
    ok = True

    # DashScope API Key
    if not os.environ.get("DASHSCOPE_API_KEY"):
        logger.error("✗ 缺少 DASHSCOPE_API_KEY 环境变量")
        ok = False
    else:
        logger.info("✓ DashScope API Key 已设置")

    # dashscope SDK
    try:
        import dashscope
        logger.info("✓ dashscope SDK 已安装")
    except ImportError:
        logger.info("⏳ 安装 dashscope SDK...")
        ret = subprocess.run(
            [sys.executable, "-m", "pip", "install", "dashscope", "-q"],
            capture_output=True, text=True
        )
        if ret.returncode == 0:
            logger.info("✓ dashscope SDK 安装成功")
        else:
            logger.error(f"✗ dashscope 安装失败: {ret.stderr}")
            ok = False

    # FFmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        logger.info("✓ FFmpeg 已安装")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.info("⏳ FFmpeg 未找到，尝试下载...")
        ret = subprocess.run(
            [sys.executable, "-m", "pip", "install", "ffmpeg-downloader", "-q"],
            capture_output=True, text=True
        )
        if ret.returncode == 0:
            subprocess.run(["ffdl", "--install"], capture_output=True, text=True)
            try:
                subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
                logger.info("✓ FFmpeg 安装成功")
            except Exception:
                logger.error("✗ FFmpeg 仍不可用，请手动安装")
                ok = False
        else:
            logger.error("✗ FFmpeg 不可用，请手动安装 https://ffmpeg.org/download.html")
            ok = False

    return ok


def generate_with_dashscope(scene, output_path):
    """调用 DashScope 通义万相视频生成"""
    import dashscope
    from dashscope.api_entities.dashscope_response import GenerationResponse

    dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]

    logger.info(f"  场景 {scene['id']}/6: 提交生成任务...")

    try:
        # 通义万相 文生视频
        response = dashscope.VideoSynthesis.call(
            model="wanx2.1-t2v-turbo",  # 通义万相文生视频模型
            prompt=scene["prompt"],
            size="1280*720",  # width*height 格式
            duration=scene["duration"],
        )

        if response.status_code != 200:
            logger.error(f"  ✗ API 返回异常: {response.status_code} {response.message}")
            return None

        task_id = response.output.task_id
        logger.info(f"  ✓ 任务已提交, TaskId: {task_id}")

        # 异步轮询
        for attempt in range(120):  # 最多等 20 分钟
            time.sleep(10)
            status_resp = dashscope.VideoSynthesis.get(task_id=task_id)

            if status_resp.status_code != 200:
                logger.error(f"  ✗ 查询失败: {status_resp.status_code}")
                return None

            status = status_resp.output.task_status
            if status == "SUCCEEDED":
                video_url = status_resp.output.video_url
                if not video_url:
                    logger.error("  ✗ 任务成功但无视频URL")
                    return None
                logger.info(f"  ✓ 视频生成完成, 下载中...")
                _download_file(video_url, output_path)
                logger.info(f"  ✓ 场景 {scene['id']} 已保存: {output_path}")
                return output_path
            elif status in ("FAILED", "CANCELED"):
                err_msg = status_resp.output.get("message", "未知错误")
                logger.error(f"  ✗ 生成失败: {status} - {err_msg}")
                return None

            if attempt % 12 == 0:  # 每 2 分钟提示一次
                logger.info(f"  生成中... ({attempt * 10}s / 状态: {status})")

        logger.error(f"  ✗ 场景 {scene['id']} 超时 (20分钟)")
        return None

    except Exception as e:
        logger.error(f"  ✗ 场景 {scene['id']} 异常: {e}")
        return None


def _download_file(url, path):
    """下载文件"""
    import urllib.request
    urllib.request.urlretrieve(url, str(path))


def merge_videos(video_paths, output_path):
    """FFmpeg 拼接"""
    logger.info("  FFmpeg 拼接视频...")
    list_path = OUTPUT_DIR / "concat_list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for vp in video_paths:
            if vp and Path(vp).exists():
                f.write(f"file '{Path(vp).absolute().as_posix()}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(list_path), "-c", "copy", str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"  ✗ 拼接失败: {result.stderr[:200]}")
        return False
    logger.info(f"  ✓ 拼接完成: {output_path}")
    return True


def add_subtitles(video_path, output_path):
    """加字幕"""
    logger.info("  生成字幕文件...")
    srt_path = OUTPUT_DIR / "subtitles.srt"
    idx = 1
    cur = 0
    with open(srt_path, "w", encoding="utf-8") as f:
        for scene in STORYBOARD:
            def _fmt(ms):
                h, r = divmod(ms, 3600)
                m, s = divmod(r, 60)
                return f"{h:02d}:{m:02d}:{s:02d},000"
            f.write(f"{idx}\n")
            f.write(f"{_fmt(cur)} --> {_fmt(cur + scene['duration'])}\n")
            f.write(f"{scene['narration']}\n\n")
            idx += 1
            cur += scene['duration']

    logger.info(f"  烧录字幕...")
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"subtitles={srt_path}",
        "-c:a", "copy",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"  ✗ 字幕失败: {result.stderr[:200]}")
        return False
    logger.info(f"  ✓ 字幕完成: {output_path}")
    return True


def generate_storyboard_md():
    """分镜表"""
    md = "# M6 Demo 分镜表\n\n"
    md += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    md += "| 场景 | 时长 | 画面 | 旁白 |\n|------|------|------|------|\n"
    for s in STORYBOARD:
        md += f"| {s['id']} | {s['duration']}s | {s['prompt'][:40]}... | {s['narration'][:30]}... |\n"
    path = OUTPUT_DIR / "storyboard.md"
    path.write_text(md, encoding="utf-8")
    logger.info(f"  ✓ 分镜表: {path}")
    return path


def main():
    print("\n" + "=" * 60)
    print("  M6 Demo 视频生成")
    print("  通义万相 × MeshIdentity × MemGuard × Polaris")
    print("=" * 60)

    # 1) 环境检查
    print("\n[Step 1] 环境检查")
    if not check_prerequisites():
        sys.exit(1)

    # 2) 分镜表
    print("\n[Step 2] 生成分镜表")
    generate_storyboard_md()

    # 3) 逐个生成
    print("\n[Step 3] 逐场景生成视频")
    video_paths = []
    for scene in STORYBOARD:
        print(f"\n  --- 场景 {scene['id']}/6 ---")
        out = OUTPUT_DIR / f"scene_{scene['id']:02d}.mp4"
        result = generate_with_dashscope(scene, out)
        video_paths.append(result)

    valid = [v for v in video_paths if v]
    if len(valid) < len(STORYBOARD):
        logger.warning(f"  ⚠ 成功 {len(valid)}/{len(STORYBOARD)} 个场景")

    # 4) 拼接
    print("\n[Step 4] 拼接视频")
    raw = OUTPUT_DIR / "demo_raw.mp4"
    if not merge_videos(valid, raw):
        sys.exit(1)

    # 5) 字幕
    print("\n[Step 5] 添加字幕")
    final = OUTPUT_DIR / "M6_Demo_Final.mp4"
    if not add_subtitles(raw, final):
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  ✅ 完成!")
    print(f"  最终视频: {final}")
    print(f"  分镜表:   {OUTPUT_DIR / 'storyboard.md'}")
    print(f"  字幕:     {OUTPUT_DIR / 'subtitles.srt'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
