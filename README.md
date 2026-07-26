<p align="center">
  <img src="assets/easygif-hero-handdrawn.png" alt="EasyGIF" width="920">
</p>

<p align="center">
  <a href="SKILL.md"><img alt="SKILL: EasyGIF" src="https://img.shields.io/badge/SKILL-EasyGIF-7B4CC2?style=for-the-badge&labelColor=555555"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/LICENSE-MIT-FF6699?style=for-the-badge&labelColor=555555"></a>
</p>

# EasyGIF

想让一张图片动起来，却不知道动作怎么设计、提示词怎么写，最后还总是卡顿、变形或发不出去？

EasyGIF 只需要一句话：它会自己设计自然动作，保持主体和画面一致，自动选择合适的制作路线，并交付可以直接发送的 GIF。

## 一分钟开始

### 快速安装

将仓库克隆到 Codex 的 Skill 目录，重启 Codex：

```bash
git clone https://github.com/Rimagination/easygif.git ~/.codex/skills/easygif
```

基础 GIF 需要 Python、Pillow；视频路线需要 `ffmpeg`。没有参考图也可以直接描述主体和动作。

### 案例一：无参考图

不提供图片，直接告诉 Codex：

```text
做一个手绘猫猫打哈欠的gif
```

<p align="center">
  <img src="gallery/cat-yawn-handdrawn.gif" alt="手绘猫猫打哈欠 GIF" width="240">
</p>

[下载猫猫打哈欠 GIF](gallery/cat-yawn-handdrawn.gif)

EasyGIF 会根据这句话自行确定主体参考、动作节奏和交付路线。

## 案例二：有参考图

提供袋熊照片作为参考图，并告诉 Codex：

### 微信表情包：袋熊挠屁股后看镜头

```text
我希望你基于这个图生成一个袋熊边挠屁股变看镜头的gif，同一只动物、同一机位、同一背景，只改变眼睛、草叶和身体的轻微动作。
```

<p align="center">
  <img src="gallery/wombat-scratch-look-wechat.gif" alt="袋熊挠屁股后看镜头微信 GIF" width="240">
</p>

EasyGIF 会锁定参考图中的主体、机位和背景，再生成和压缩最终 GIF。

## 更多案例

### 普通视觉素材：电影感光束

电影感视觉：保持城市构图，让柔和光束缓慢扫过画面。

<p align="center">
  <img src="gallery/cinematic-light-sweep.gif" alt="电影感光束扫过城市 GIF" width="480">
</p>

## 微信交付

```text
请把这些 GIF 打包成微信聊天表情，检查尺寸、大小、循环和缩略图。
```

开放平台投稿：让 EasyGIF 额外生成封面、图标和 Banner。

## 许可

本项目采用 [MIT License](LICENSE)。
