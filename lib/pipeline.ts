import path from "node:path";
import {outputDir} from "./paths";
import {localAdapters, buildStoryboard, maybeGenerateFishVoiceover} from "./adapters/local";
import {getProject, updateGeneratedProject} from "./db";
import {languages, platforms, type RenderJob, type Storyboard} from "./types";

export async function generateProject(projectId: string) {
  const project = getProject(projectId);
  if (!project) throw new Error("项目不存在");

  const blueprint = await localAdapters.visualAnalyze(project.manifest);
  const storyboards: Storyboard[] = [];
  const jobs: RenderJob[] = [];

  for (const language of languages) {
    for (let variant = 1; variant <= 3; variant += 1) {
      const script = await localAdapters.scriptRewrite(project.brief, language, variant);
      const narration = await localAdapters.tts(script, language);
      for (const platform of platforms) {
        const storyboard = buildStoryboard(
          project.brief,
          blueprint,
          script,
          language,
          platform,
          variant,
          project.manifest.assets,
        );
        const jobOutputDir = path.join(outputDir, projectId, language, platform);
        if (project.brief.generationMode === "api") {
          const prompts = await localAdapters.shotPrompts(storyboard, project.brief);
          storyboard.seedanceClips = await localAdapters.generateVideoClips(
            prompts,
            storyboard,
            path.join(jobOutputDir, "seedance"),
          );
          storyboard.voiceoverPath = await maybeGenerateFishVoiceover(
            storyboard,
            script,
            path.join(jobOutputDir, "voice"),
          );
        }
        storyboards.push(storyboard);
        const job: RenderJob = {
          id: `${projectId}-${language}-${platform}-${variant}`,
          projectId,
          language,
          platform,
          variant,
          status: "rendering",
        };
        void narration;
        try {
          const result = await localAdapters.render(
            storyboard,
            job,
            jobOutputDir,
          );
          jobs.push(result);
        } catch (error) {
          jobs.push({
            ...job,
            status: "failed",
            error: error instanceof Error ? error.message : "未知渲染错误",
          });
        }
      }
    }
  }

  return updateGeneratedProject(projectId, blueprint, storyboards, jobs);
}
