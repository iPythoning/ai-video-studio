import {DatabaseSync} from "node:sqlite";
import {existsSync, mkdirSync} from "node:fs";
import path from "node:path";
import {dataDir, dbPath} from "./paths";
import type {
  AssetManifest,
  ProjectBrief,
  ProjectRecord,
  RenderJob,
  Storyboard,
  StyleBlueprint,
} from "./types";

let db: DatabaseSync | null = null;

function json<T>(value: T): string {
  return JSON.stringify(value);
}

function parseJson<T>(value: unknown, fallback: T): T {
  if (typeof value !== "string" || value.length === 0) return fallback;
  return JSON.parse(value) as T;
}

export function getDb() {
  if (!existsSync(dataDir)) mkdirSync(dataDir, {recursive: true});
  db ??= new DatabaseSync(dbPath);
  db.exec(`
    CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY,
      created_at TEXT NOT NULL,
      brief_json TEXT NOT NULL,
      manifest_json TEXT NOT NULL,
      blueprint_json TEXT,
      storyboards_json TEXT NOT NULL DEFAULT '[]',
      jobs_json TEXT NOT NULL DEFAULT '[]'
    );
  `);
  return db;
}

export function insertProject(brief: ProjectBrief, manifest: AssetManifest) {
  const id = manifest.projectId;
  const createdAt = manifest.createdAt;
  getDb()
    .prepare(
      "INSERT INTO projects (id, created_at, brief_json, manifest_json) VALUES (?, ?, ?, ?)",
    )
    .run(id, createdAt, json(brief), json(manifest));
  return getProject(id);
}

export function updateGeneratedProject(
  id: string,
  blueprint: StyleBlueprint,
  storyboards: Storyboard[],
  jobs: RenderJob[],
) {
  getDb()
    .prepare(
      "UPDATE projects SET blueprint_json = ?, storyboards_json = ?, jobs_json = ? WHERE id = ?",
    )
    .run(json(blueprint), json(storyboards), json(jobs), id);
  return getProject(id);
}

export function listProjects() {
  const rows = getDb()
    .prepare("SELECT id, created_at, brief_json, manifest_json, blueprint_json, storyboards_json, jobs_json FROM projects ORDER BY created_at DESC")
    .all();
  return rows.map(rowToProject);
}

export function getProject(id: string) {
  const row = getDb()
    .prepare("SELECT id, created_at, brief_json, manifest_json, blueprint_json, storyboards_json, jobs_json FROM projects WHERE id = ?")
    .get(id);
  return row ? rowToProject(row) : null;
}

function rowToProject(row: Record<string, unknown>): ProjectRecord {
  return {
    id: String(row.id),
    createdAt: String(row.created_at),
    brief: parseJson<ProjectBrief>(row.brief_json, {
      productName: "",
      targetAudience: "",
      sellingPoints: "",
      tone: "",
      sourceScript: "",
      scenario: "",
      generationMode: "local",
      forbiddenWords: [],
      targetPlatforms: ["tiktok", "reels", "shorts"],
    }),
    manifest: parseJson<AssetManifest>(row.manifest_json, {
      projectId: String(row.id),
      createdAt: String(row.created_at),
      assets: [],
    }),
    blueprint: parseJson<StyleBlueprint | undefined>(row.blueprint_json, undefined),
    storyboards: parseJson<Storyboard[]>(row.storyboards_json, []),
    jobs: parseJson<RenderJob[]>(row.jobs_json, []),
  };
}
