import {NextResponse} from "next/server";
import {generateProject} from "@/lib/pipeline";

export const runtime = "nodejs";

export async function POST(_: Request, context: {params: Promise<{id: string}>}) {
  const {id} = await context.params;
  try {
    const project = await generateProject(id);
    return NextResponse.json({project});
  } catch (error) {
    return NextResponse.json(
      {error: error instanceof Error ? error.message : "生成失败"},
      {status: 500},
    );
  }
}
