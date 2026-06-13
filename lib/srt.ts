import type {Storyboard} from "./types";

function timecode(sec: number) {
  const clamped = Math.max(0, sec);
  const hours = Math.floor(clamped / 3600);
  const minutes = Math.floor((clamped % 3600) / 60);
  const seconds = Math.floor(clamped % 60);
  const millis = Math.round((clamped - Math.floor(clamped)) * 1000);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")},${String(millis).padStart(3, "0")}`;
}

export function storyboardToSrt(storyboard: Storyboard) {
  return storyboard.scenes
    .map((scene, index) => {
      const start = timecode(scene.startSec);
      const end = timecode(scene.startSec + scene.durationSec);
      return `${index + 1}\n${start} --> ${end}\n${scene.caption}\n`;
    })
    .join("\n");
}
