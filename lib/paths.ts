import path from "node:path";
import {mkdir} from "node:fs/promises";

export const dataDir = path.join(process.cwd(), "data");
export const uploadDir = path.join(dataDir, "uploads");
export const outputDir = path.join(dataDir, "outputs");
export const dbPath = path.join(dataDir, "clipforge.sqlite");

export async function ensureDataDirs() {
  await mkdir(uploadDir, {recursive: true});
  await mkdir(outputDir, {recursive: true});
}
