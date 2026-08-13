import type { LessonContent } from "@/types";

export type VideoAspect = "16:9" | "9:16";

export const VIDEO_ASPECTS: Record<
  VideoAspect,
  { width: number; height: number; label: string; hint: string }
> = {
  "16:9": { width: 1280, height: 720, label: "16:9", hint: "Landscape" },
  "9:16": { width: 720, height: 1280, label: "9:16", hint: "Phone / Reels" },
};

export function videoDimensions(aspect: VideoAspect) {
  return VIDEO_ASPECTS[aspect];
}

export function sceneMediaUrl(
  sceneId: string,
  aspect: VideoAspect,
  urls: Record<string, string>,
  portraitUrls: Record<string, string> = {},
) {
  if (aspect === "9:16" && portraitUrls[sceneId]) return portraitUrls[sceneId];
  return urls[sceneId];
}

export function storyNarration(content: LessonContent): string[] {
  return content.sections.flatMap((section) =>
    section.paragraphs
      .map((paragraph) => {
        const fromSentences = paragraph.sentences.map((sentence) => sentence.text).join(" ").trim();
        return (paragraph.text || fromSentences).replace(/\s+/g, " ").trim();
      })
      .filter(Boolean),
  );
}

export function sceneIndexForParagraph(
  paragraphIndex: number,
  paragraphCount: number,
  sceneCount: number,
) {
  if (!sceneCount) return -1;
  if (paragraphCount <= 1) return 0;
  const ratio = paragraphIndex / Math.max(1, paragraphCount - 1);
  return Math.min(sceneCount - 1, Math.max(0, Math.round(ratio * (sceneCount - 1))));
}

export function recorderMimeType(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  const types = [
    "video/webm;codecs=vp9,opus",
    "video/webm;codecs=vp8,opus",
    "video/webm;codecs=vp9",
    "video/webm;codecs=vp8",
    "video/webm",
    "video/mp4",
  ];
  return types.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
}
