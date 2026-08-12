"use client";

import { memo, useEffect, useRef } from "react";
import { Download } from "lucide-react";
import { cn } from "@/lib/utils";
import { htmlLang } from "@/lib/speech";
import { downloadSceneImage, sceneIndexForParagraph } from "@/components/story-illustrations";
import { Button } from "@/components/ui/button";
import { useReaderStore } from "@/store/reader-store";
import type { LessonContent, Paragraph, StoryIllustration } from "@/types";

const NOISE_WORD = /^[\W_|~`^=*#@+$\\/<>[\]{}©®™•·…“”"'`´]+$|^[Il1|]{3,}$/;

function isNoiseWord(text: string) {
  const trimmed = text.trim();
  return !trimmed || NOISE_WORD.test(trimmed);
}

const WordSpan = memo(function WordSpan({
  id,
  text,
  isActive,
  highlightable,
}: {
  id: string;
  text: string;
  isActive: boolean;
  highlightable: boolean;
}) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (isActive && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    }
  }, [isActive]);

  return (
    <span
      ref={ref}
      data-word-id={id}
      className={cn(
        highlightable && "inline-block rounded-md px-0.5 transition-all duration-150",
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
}: {
  paragraph: Paragraph;
  activeWordId: string | null;
  activeParagraphId: string | null;
  highlightWords: boolean;
}) {
  const isActivePara = activeParagraphId === paragraph.id;
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (isActivePara && !highlightWords && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [isActivePara, highlightWords]);

  return (
    <p
      ref={ref}
      data-paragraph-id={paragraph.id}
      className={cn(
        "mb-5 text-lg leading-relaxed text-teal-950 md:text-xl md:leading-8",
        isActivePara && !highlightWords && "rounded-2xl bg-amber-50 px-3 py-2",
      )}
    >
      {paragraph.sentences.map((sentence) => (
        <span key={sentence.id} data-sentence-id={sentence.id}>
          {sentence.words.map((word) =>
            isNoiseWord(word.text) ? null : (
            <WordSpan
              key={word.id}
              id={word.id}
              text={word.text}
              isActive={highlightWords && activeWordId === word.id}
              highlightable={highlightWords}
            />
            ),
          )}
        </span>
      ))}
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
  const playbackStyle = useReaderStore((s) => s.playbackStyle);
  const highlightWords = playbackStyle !== "direct";
  const hasWords = content.sections.some((s) => s.paragraphs.some((p) => p.sentences.some((sent) => sent.words.length)));
  const paragraphs = content.sections.flatMap((section) => section.paragraphs);

  if (!hasWords) {
    return (
      <p className="text-teal-900/70">
        I don&apos;t have the story words yet. Go back to Preview, keep the text, and tap Start learning
        again.
      </p>
    );
  }

  let paragraphCursor = 0;
  const shownScenes = new Set<number>();

  return (
    <article className="prose-lesson max-w-none" aria-live="polite" lang={htmlLang(content.language)}>
      {content.sections.map((section) => (
        <section key={section.id} className="mb-8">
          {section.heading ? (
            <h2 className="font-display mb-4 text-2xl font-bold text-teal-950 md:text-3xl">
              {section.heading}
            </h2>
          ) : null}
          {section.paragraphs.map((p) => {
            const pIndex = paragraphCursor;
            paragraphCursor += 1;
            const sceneIdx = sceneIndexForParagraph(pIndex, paragraphs.length, scenes.length);
            const scene = sceneIdx >= 0 && !shownScenes.has(sceneIdx) ? scenes[sceneIdx] : null;
            if (sceneIdx >= 0) shownScenes.add(sceneIdx);
            return (
              <div key={p.id}>
                {scene && urls[scene.id] ? (
                  <figure className="mb-4 overflow-hidden rounded-2xl border border-teal-900/10 bg-teal-50/60">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={urls[scene.id]}
                      alt={scene.caption}
                      className="max-h-72 w-full object-cover"
                    />
                    <figcaption className="flex items-center justify-between gap-2 px-3 py-2 text-sm text-teal-900/80">
                      <span>
                        Picture {scene.position + 1}: {scene.caption}
                      </span>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          downloadSceneImage(
                            urls[scene.id],
                            `story-scene-${scene.position + 1}.png`,
                          )
                        }
                      >
                        <Download className="h-3.5 w-3.5" />
                        Save
                      </Button>
                    </figcaption>
                  </figure>
                ) : null}
                <ParagraphBlock
                  paragraph={p}
                  activeWordId={activeWordId}
                  activeParagraphId={activeParagraphId}
                  highlightWords={highlightWords}
                />
              </div>
            );
          })}
        </section>
      ))}
    </article>
  );
}
