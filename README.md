# ClipForge Local

本地优先的营销短视频自动剪辑工作台 MVP。上传文案、素材和对标视频后，系统会生成中英双语、TikTok / Reels / Shorts 三平台、每种语言三组变体的输出包。

当前版本已经合并 `iPythoning/ai-video-studio` 的核心思路：Seedance 2.0 生成视频片段、Fish Audio 生成人声、FFmpeg/Remotion 合成导出。默认是本地预览模式，不消耗外部 API；创建项目时选择“API 增强”才会调用 Seedance/Fish。

## 运行

```bash
npm install
npm run dev
```

打开 `http://localhost:3000`。

如果 3000 被占用，Next.js 会自动切到下一个可用端口。

## API 增强模式

复制 `.env.example` 为 `.env.local`，填入：

```bash
SEEDANCE_API_KEY=...
FISH_AUDIO_API_KEY=...
FISH_AUDIO_VOICE_ZH=...
FISH_AUDIO_VOICE_EN=...
```

然后在 Web 工作台的“生成模式”选择 `API 增强：Seedance + Fish Audio`。为了避免误烧额度，Seedance 默认只给 `中文 / TikTok / V1` 这条主故事板生成最多 3 个视频片段，其余平台和变体复用本地合成链路。

## 输出

生成结果写入 `data/outputs/<projectId>/`，包含：

- 9:16 MP4 占位成片
- SRT 字幕
- 平台标题、描述、标签和质检报告
- 从对标视频抽象出的 `Style Blueprint`

## 架构

- Next.js Web 工作台
- Node.js API 路由负责上传、任务编排和输出
- Node 内置 SQLite 保存项目、素材清单、风格蓝图、分镜和任务
- FFmpeg 生成本地可播放 MP4
- Remotion 模板位于 `remotion/`，后续可替换当前 FFmpeg 占位渲染器
- AI 能力通过 `AdapterSet` 抽象，默认本地确定性实现；API 增强模式可调用 Seedance 2.0 和 Fish Audio，后续还可替换为 WhisperX、NLLB、OpenAI、DeepL、ElevenLabs 等

## 上游合并

见 `NOTICE.md`。本项目吸收了 `iPythoning/ai-video-studio` 的 MIT 代码思路，但没有复制其 `reference/huobao/` 下的 CC BY-NC-SA 非商业 prompt 文档。

## 验证

```bash
npm run test
npm run build
```
