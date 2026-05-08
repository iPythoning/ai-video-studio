import {Composition, Folder} from "remotion";
import {ShortVideo, defaultStoryboard} from "./ShortVideo";

export function RemotionRoot() {
  return (
    <Folder name="Social">
      <Composition
        id="MarketingShort"
        component={ShortVideo}
        durationInFrames={720}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{storyboard: defaultStoryboard}}
      />
    </Folder>
  );
}
