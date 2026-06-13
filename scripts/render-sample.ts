import {bundle} from "@remotion/bundler";
import {renderMedia, selectComposition} from "@remotion/renderer";
import path from "node:path";

const serveUrl = await bundle({
  entryPoint: path.join(process.cwd(), "remotion", "Root.tsx"),
  webpackOverride: (config) => config,
});

const composition = await selectComposition({
  serveUrl,
  id: "MarketingShort",
});

await renderMedia({
  composition,
  serveUrl,
  codec: "h264",
  outputLocation: path.join(process.cwd(), "data", "outputs", "sample-remotion.mp4"),
});

console.log("Rendered data/outputs/sample-remotion.mp4");
