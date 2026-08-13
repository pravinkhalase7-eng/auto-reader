"use client";

import { memo, useEffect, useRef, type RefObject } from "react";
import { Download } from "lucide-react";
import { cn } from "@/lib/utils";
import { htmlLang } from "@/lib/speech";
import { clearHoverTimer, previewWord, scheduleWordPreview } from "@/lib/preview-word";
import { downloadSceneImage, sceneIndexForParagraph } from "@/components/story-illustrations";
import { Button } from "@/components/ui/button";
import { useReaderStore } from "@/store/reader-store";
import type { LessonContent, Paragraph, StoryIllustration } from "@/types";

function isNoiseWord(text: string) {
  const trimmed = text.trim();
  if (!trimmed) return true;
  // Keep letters in any script (Hindi, Marathi, English). Drop punctuation-only OCR junk.
  if (/^[\p{P}\p{S}\p{Zs}]+$/u.test(trimmed)) return true;
  return /^[Il1|]{3,}$/.test(trimmed);
}

function scrollChildIntoPane(container: HTMLElement, el: HTMLElement) {
  const pane = container.getBoundingClientRect();
  const box = el.getBoundingClientRect();
  const pad = 16;
  if (box.top >= pane.top + pad && box.bottom <= pane.bottom - pad) return;
  const target = pane.top + pane.height * 0.28;
  container.scrollTo({
    top: container.scrollTop + (box.top - target),
    behavior: "smooth",
  });
}

const WordSpan = memo(function WordSpan({
  id,
  text,
  isActive,
  highlightable,
  language,
}: {
  id: string;
  text: string;
  isActive: boolean;
  highlightable: boolean;
  language: string;
}) {
  const isPlaying = useReaderStore((s) => s.isPlaying);
  const volume = useReaderStore((s) => s.volume);
  const preferredVoiceURI = useReaderStore((s) => s.preferredVoiceURI);

  function speakThisWord() {
    if (isPlaying) return;
    void previewWord({
      text,
      language,
      volume,
      preferredVoiceURI,
    });
  }

  return (
    <span
      data-word-id={id}
      title={isPlaying ? undefined : "Click to hear this word"}
      onClick={(event) => {
        if (isPlaying) return;
        event.preventDefault();
        speakThisWord();
      }}
      onPointerEnter={() => {
        if (isPlaying) return;
        scheduleWordPreview({
          text,
          language,
          volume,
          preferredVoiceURI,
        });
      }}
      onPointerLeave={() => clearHoverTimer()}
      className={cn(
        highlightable && "inline-block rounded-md px-0.5 transition-all duration-150",
        !isPlaying && "cursor-pointer hover:bg-amber-100",
        isActive && "scale-110 bg-amber-300 text-teal-950 shadow-sm",
      )}
    >
      {text}{" "}
    </span>
  );
});

function ParagraphBlock({
  paragraph,
  activeWordId,
  activeParagraphId,
  highlightWords,
  scrollPane,
  language,
}: {
  paragraph: Paragraph;
  activeWordId: string | null;
  activeParagraphId: string | null;
  highlightWords: boolean;
  scrollPane: RefObject<HTMLDivElement | null>;
  language: string;
}) {
  const isActivePara = activeParagraphId === paragraph.id;
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (!isActivePara || !ref.current || !scrollPane.current) return;
    scrollChildIntoPane(scrollPane.current, ref.current);
  }, [isActivePara, highlightWords, scrollPane]);

  const visibleWords = paragraph.sentences.flatMap((sentence) =>
    sentence.words.filter((word) => !isNoiseWord(word.text)),
  );
  const fallbackText = paragraph.text?.trim();

  return (
    <p
      ref={ref}
      data-paragraph-id={paragraph.id}
      className={cn(
        "mb-5 scroll-mt-2 text-lg leading-relaxed text-teal-950 md:text-xl md:leading-8",
        isActivePara && "rounded-2xl bg-amber-50 px-3 py-2 ring-2 ring-amber-300",
      )}
    >
      {visibleWords.length
        ? paragraph.sentences.map((sentence) => (
            <span key={sentence.id} data-sentence-id={sentence.id}>
              {sentence.words.map((word) =>
                isNoiseWord(word.text) ? null : (
                  <WordSpan
                    key={word.id}
                    id={word.id}
                    text={word.text}
                    isActive={highlightWords && activeWordId === word.id}
                    highlightable={highlightWords}
                    language={language}
                  />
                ),
              )}
            </span>
          ))
        : fallbackText || null}
    </p>
  );
}

export function LessonViewer({
  content,
  scenes = [],
  urls = {},
}: {
  content: LessonContent;
  scenes?: StoryIllustration[];
  urls?: Record<string, string>;
}) {
  const activeWordId = useReaderStore((s) => s.activeWordId);
  const activeParagraphId = useReaderStore((s) => s.activeParagraphId);
  const paragraphIndex = useReaderStore((s) => s.paragraphIndex);
  const playbackStyle = useReaderStore((s) => s.playbackStyle);
  const highlightWords = playbackStyle !== "direct";
  const scrollPane = useRef<HTMLDivElement>(null);
  const hasWords = content.sections.some((s) =>
    s.paragraphs.some((p) => p.sentences.some((sent) => sent.words.length)),
  );
  const paragraphs = content.sections.flatMap((section) => section.paragraphs);
  const sceneIdx = sceneIndexForParagraph(paragraphIndex, paragraphs.length, scenes.length);
  const scene = sceneIdx >= 0 ? scenes[sceneIdx] : null;
  const sceneUrl = scene ? urls[scene.id] : undefined;

  if (!hasWords) {
    return (
      <p className="text-teal-900/70">
        I don&apos;t have the story words yet. Go back to Preview, keep the text, and tap Start learning
        again.
      </p>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      {sceneUrl ? (
        <figure className="relative mb-4 flex max-h-72 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-teal-900/10 bg-teal-50 md:max-h-80">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={sceneUrl}
            alt=""
            className="max-h-72 w-full object-contain object-center md:max-h-80"
          />
          <Button
            size="sm"
            variant="outline"
            className="absolute right-2 top-2 bg-white/90"
            onClick={() =>
              downloadSceneImage(sceneUrl, `story-scene-${(scene?.position ?? 0) + 1}.png`)
            }
          >
            <Download className="h-3.5 w-3.5" />
            Save
          </Button>
        </figure>
      ) : null}

      <div ref={scrollPane} data-lesson-scroll className="min-h-0 flex-1 overflow-y-auto pr-1">
        <p className="mb-3 text-xs text-teal-800/70">
          Hover a word, or click it, to hear how it sounds.
        </p>
        <article
          className="prose-lesson max-w-none"
          aria-live="polite"
          lang={htmlLang(content.language)}
          style={
            content.language === "hi" || content.language === "mr"
              ? {
                  fontFamily:
                    '"Nirmala UI", "Noto Sans Devanagari", "Kohinoor Devanagari", "Mangal", var(--font-sans), sans-serif',
                }
              : undefined
          }
        >
          {content.sections.map((section) => (
            <section key={section.id} className="mb-8">
              {section.heading ? (
                <h2
                  className={cn(
                    "mb-4 text-2xl font-bold text-teal-950 md:text-3xl",
                    content.language === "hi" || content.language === "mr" ? "" : "font-display",
                  )}
                >
                  {section.heading}
                </h2>
              ) : null}
              {section.paragraphs.map((p) => (
                <ParagraphBlock
                  key={p.id}
                  paragraph={p}
                  activeWordId={activeWordId}
                  activeParagraphId={activeParagraphId}
                  highlightWords={highlightWords}
                  scrollPane={scrollPane}
                  language={content.language}
                />
              ))}
            </section>
          ))}
        </article>
      </div>
    </div>
  );
}
