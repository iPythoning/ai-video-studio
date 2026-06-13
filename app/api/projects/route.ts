import {NextRequest, NextResponse} from "next/server";
import path from "node:path";
import {randomUUID} from "node:crypto";
import {mkdir, writeFile} from "node:fs/promises";
import {insertProject, listProjects} from "@/lib/db";
import {ensureDataDirs, uploadDir} from "@/lib/paths";
import {inferAssetKind, probeAsset, sanitizeFileName} from "@/lib/media";
import type {AssetItem, Platform, ProjectBrief} from "@/lib/types";

export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json({projects: listProjects()});
}

export async function POST(request: NextRequest) {
  await ensureDataDirs();
  const form = await request.formData();
  const projectId = randomUUID();
  const createdAt = new Date().toISOString();
  const projectDir = path.join(uploadDir, projectId);
  await mkdir(projectDir, {recursive: true});

  const brief: ProjectBrief = {
    productName: value(form, "productName") || "未命名产品",
    targetAudience: value(form, "targetAudience") || "社媒受众",
    sellingPoints: value(form, "sellingPoints") || "节省剪辑时间，快速测试创意",
    tone: value(form, "tone") || "直接可信",
    sourceScript: value(form, "sourceScript"),
    scenario: value(form, "scenario"),
    generationMode: value(form, "generationMode") === "api" ? "api" : "local",
    forbiddenWords: value(form, "forbiddenWords")
      .split(/[,\n，]+/)
      .map((word) => word.trim())
      .filter(Boolean),
    targetPlatforms: ["tiktok", "reels", "shorts"] satisfies Platform[],
  };

  const assets: AssetItem[] = [];
  const normalFiles = form.getAll("assets").filter(isFileWithName);
  const referenceFiles = form.getAll("reference").filter(isFileWithName);

  for (const file of [...normalFiles, ...referenceFiles]) {
    const isReference = referenceFiles.includes(file);
    const fileName = sanitizeFileName(file.name);
    const assetPath = path.join(projectDir, `${randomUUID()}-${fileName}`);
    const buffer = Buffer.from(await file.arrayBuffer());
    await writeFile(assetPath, buffer);
    const asset: AssetItem = {
      id: randomUUID(),
      kind: inferAssetKind(file.name, file.type, isReference),
      fileName,
      path: assetPath,
      mimeType: file.type || "application/octet-stream",
      sizeBytes: file.size,
      status: "ready",
    };
    assets.push(await probeAsset(asset));
  }

  const referenceAssetId = assets.find((asset) => asset.kind === "reference")?.id;
  const project = insertProject(brief, {projectId, createdAt, assets, referenceAssetId});
  return NextResponse.json({project}, {status: 201});
}

function value(form: FormData, key: string) {
  const item = form.get(key);
  return typeof item === "string" ? item.trim() : "";
}

function isFileWithName(value: FormDataEntryValue): value is File {
  return value instanceof File && value.name.length > 0 && value.size > 0;
}
