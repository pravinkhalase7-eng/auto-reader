import type { LessonContent } from "@/types";

export const VIDEO_WIDTH = 1280;
export const VIDEO_HEIGHT = 720;

export function wrapCaption(text: string, maxChars = 54, maxLines = 3): string[] {
  const words = text.trim().split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length > maxChars && current) {
      lines.push(current);
      current = word;
      if (lines.length === maxLines) break;
    } else {
      current = next;
    }
  }
  if (current && lines.length < maxLines) lines.push(current);
  if (lines.length === maxLines) {
    const used = lines.join(" ").split(/\s+/).length;
    if (used < words.length) {
      lines[maxLines - 1] = `${lines[maxLines - 1].replace(/[.…]*$/, "")}…`;
    }
  }
  return lines;
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
    "video/webm;codecs=vp9",
    "video/webm;codecs=vp8",
    "video/webm",
    "video/mp4",
  ];
  return types.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
}
