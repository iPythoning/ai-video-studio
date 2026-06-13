"use client";

import {useEffect, useMemo, useState} from "react";
import {
  BadgeCheck,
  Clapperboard,
  FileVideo,
  Languages,
  PackageCheck,
  Play,
  Upload,
  WandSparkles,
} from "lucide-react";
import type {ProjectRecord, RenderJob} from "@/lib/types";

type ApiProject = {project: ProjectRecord};
type IntegrationStatus = {
  integrations: {
    seedance: {configured: boolean; model: string; maxClipsPerStoryboard: number};
    fishAudio: {configured: boolean; model: string; zhVoiceConfigured: boolean; enVoiceConfigured: boolean};
  };
};

const steps = [
  ["上传素材", "文案、图片、视频、对标视频入库"],
  ["生成分镜", "脚本拆解为镜头和字幕"],
  ["分析对标", "提取节奏、版式和 CTA"],
  ["自动剪辑", "按语言、平台、变体生成"],
  ["可编辑预览", "检查字幕安全区和文案"],
  ["批量导出", "MP4、SRT、封面、报告"],
];

const platformName = {
  tiktok: "TikTok",
  reels: "Reels",
  shorts: "Shorts",
};

const languageName = {
  zh: "中文",
  en: "English",
};

export function Studio() {
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationStatus["integrations"] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/integrations")
      .then((response) => response.json())
      .then((data: IntegrationStatus) => setIntegrations(data.integrations))
      .catch(() => setIntegrations(null));
  }, []);

  const completedJobs = useMemo(
    () => project?.jobs.filter((job) => job.status === "completed") ?? [],
    [project],
  );

  async function createProject(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/projects", {method: "POST", body: form});
      const data = (await response.json()) as Partial<ApiProject> & {error?: string};
      if (!response.ok || !data.project) throw new Error(data.error || "项目创建失败");
      setProject(data.project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "项目创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    if (!project) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/projects/${project.id}/generate`, {method: "POST"});
      const data = (await response.json()) as Partial<ApiProject> & {error?: string};
      if (!response.ok || !data.project) throw new Error(data.error || "生成失败");
      setProject(data.project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="mark">
            <Clapperboard size={25} />
          </div>
          <div>
            <h1>ClipForge Local</h1>
            <p>本地优先的多语言社媒短视频自动剪辑工作台</p>
          </div>
        </div>
        <p>开源优先 · 可替换模型 · 9:16 批量输出</p>
      </header>

      <section className="grid">
        <form className="panel" onSubmit={createProject}>
          <h2>创建视频项目</h2>
          <label className="field">
            <span>产品 / 服务</span>
            <input name="productName" placeholder="例如：PulseAgent 数字员工" required />
          </label>
          <div className="row">
            <label className="field">
              <span>目标受众</span>
              <input name="targetAudience" placeholder="跨境卖家、SaaS 团队" />
            </label>
            <label className="field">
              <span>语气</span>
              <select name="tone" defaultValue="直接可信">
                <option>直接可信</option>
                <option>高能转化</option>
                <option>专业克制</option>
                <option>创作者口吻</option>
              </select>
            </label>
          </div>
          <label className="field">
            <span>卖点</span>
            <textarea
              name="sellingPoints"
              placeholder="输入核心收益、使用场景、差异化、CTA"
              required
            />
          </label>
          <label className="field">
            <span>原始文案</span>
            <textarea name="sourceScript" placeholder="可直接粘贴广告脚本、口播稿、落地页文案" />
          </label>
          <label className="field">
            <span>使用场景</span>
            <input name="scenario" placeholder="晨跑 / 地铁 / 办公室 / 加班，或具体剧情场景" />
          </label>
          <label className="field">
            <span>生成模式</span>
            <select name="generationMode" defaultValue="local">
              <option value="local">本地预览：不消耗 API</option>
              <option value="api">API 增强：Seedance + Fish Audio</option>
            </select>
          </label>
          <IntegrationStrip integrations={integrations} />
          <label className="field">
            <span>禁用词</span>
            <input name="forbiddenWords" placeholder="用逗号分隔" />
          </label>
          <label className="field uploadBox">
            <span>图片 / 视频 / 音频素材</span>
            <input name="assets" type="file" accept="image/*,video/*,audio/*" multiple />
          </label>
          <label className="field uploadBox">
            <span>对标视频</span>
            <input name="reference" type="file" accept="video/*" />
          </label>
          <div className="actions">
            <button className="primary" disabled={busy} type="submit">
              <Upload size={18} />
              建立素材清单
            </button>
            <button className="secondary" disabled={busy || !project} onClick={generate} type="button">
              <WandSparkles size={18} />
              生成短视频包
            </button>
          </div>
          {error ? <div className="error">{error}</div> : null}
        </form>

        <div className="work">
          <section className="heroBand">
            <div className="heroCopy">
              <div>
                <p className="legend">Marketing Video Automation</p>
                <h2>一份素材，生成多语言、多平台、可测试短视频。</h2>
              </div>
              <p>
                对标视频只会变成风格蓝图；系统抽取节奏、安全区、字幕和 CTA 结构，再用你自己的素材生成可发布变体。
              </p>
            </div>
            <div className="phone" aria-hidden="true">
              <div className="phoneText">
                Hook
                <br />
                Caption
                <br />
                CTA
              </div>
            </div>
          </section>

          <section className="preview">
            <h2>工作流状态</h2>
            <div className="steps">
              {steps.map(([title, body], index) => (
                <div className="step" key={title}>
                  <b>{index + 1}. {title}</b>
                  <span>{body}</span>
                </div>
              ))}
            </div>
          </section>

          {project ? (
            <>
              <ProjectSummary project={project} integrations={integrations} />
              <Blueprint project={project} />
              <Jobs jobs={completedJobs} />
            </>
          ) : (
            <section className="preview">
              <h2>等待素材</h2>
              <p className="notice">
                先创建项目。生成完成后，这里会显示素材清单、风格蓝图、分镜结果和每个平台的输出包。
              </p>
            </section>
          )}
        </div>
      </section>
    </main>
  );
}

function IntegrationStrip({integrations}: {integrations: IntegrationStatus["integrations"] | null}) {
  const seedance = integrations?.seedance.configured ? "Seedance 已配置" : "Seedance 未配置";
  const fish = integrations?.fishAudio.configured ? "Fish Audio 已配置" : "Fish Audio 未配置";
  return (
    <div className="apiStrip">
      <span>{seedance}</span>
      <span>{fish}</span>
      <span>API 增强只在手动选择后启用</span>
    </div>
  );
}

function ProjectSummary({
  project,
  integrations,
}: {
  project: ProjectRecord;
  integrations: IntegrationStatus["integrations"] | null;
}) {
  return (
    <section className="preview">
      <h2>项目资产</h2>
      <div className="blueprint">
        <Metric icon={<FileVideo size={18} />} label="素材" value={`${project.manifest.assets.length} 个`} />
        <Metric icon={<Languages size={18} />} label="语言" value="中文 / EN" />
        <Metric icon={<PackageCheck size={18} />} label="输出任务" value={`${project.jobs.length || 18} 个`} />
        <Metric icon={<BadgeCheck size={18} />} label="状态" value={project.jobs.length ? "已生成" : "待生成"} />
        <Metric label="模式" value={project.brief.generationMode === "api" ? "API 增强" : "本地预览"} />
        <Metric
          label="人声"
          value={project.brief.generationMode === "api" && integrations?.fishAudio.configured ? "Fish Audio" : "占位音轨"}
        />
      </div>
    </section>
  );
}

function Blueprint({project}: {project: ProjectRecord}) {
  const blueprint = project.blueprint;
  if (!blueprint) return null;
  return (
    <section className="preview">
      <h2>Style Blueprint</h2>
      <div className="blueprint">
        <Metric label="来源" value={blueprint.source === "reference-video" ? "对标视频" : "默认风格"} />
        <Metric label="时长" value={`${blueprint.targetDurationSec}s`} />
        <Metric label="镜头" value={`${blueprint.sceneCount} 段`} />
        <Metric label="字幕" value={blueprint.captionPosition} />
        <Metric label="B-roll" value={blueprint.bRollDensity} />
        <Metric label="CTA" value={`${blueprint.ctaAtSec}s`} />
        <Metric label="人声" value={`${blueprint.audioMix.voiceDb}dB`} />
        <Metric label="音乐" value={`${blueprint.audioMix.musicDb}dB`} />
        <Metric label="Seedance" value={`${project.storyboards[0]?.seedanceClips?.length || 0} 段`} />
      </div>
    </section>
  );
}

function Jobs({jobs}: {jobs: RenderJob[]}) {
  if (jobs.length === 0) return null;
  return (
    <section className="preview">
      <h2>输出包</h2>
      <div className="jobs">
        {jobs.map((job) => (
          <article className="job" key={job.id}>
            <div className="jobHead">
              <strong>
                {languageName[job.language]} · {platformName[job.platform]} · V{job.variant}
              </strong>
              <span className="pill">{job.status}</span>
            </div>
            <ul>
              <li>MP4: {shortPath(job.outputPath)}</li>
              <li>SRT: {shortPath(job.srtPath)}</li>
              <li>报告: {shortPath(job.reportPath)}</li>
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}

function Metric({
  icon,
  label,
  value,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="metric">
      <span className="legend">{icon} {label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function shortPath(value?: string) {
  if (!value) return "未生成";
  const marker = "/data/outputs/";
  const index = value.indexOf(marker);
  return index >= 0 ? value.slice(index + marker.length) : value;
}
