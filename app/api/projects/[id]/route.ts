import {NextResponse} from "next/server";
import {getProject} from "@/lib/db";

export const runtime = "nodejs";

export async function GET(_: Request, context: {params: Promise<{id: string}>}) {
  const {id} = await context.params;
  const project = getProject(id);
  if (!project) {
    return NextResponse.json({error: "项目不存在"}, {status: 404});
  }
  return NextResponse.json({project});
}
