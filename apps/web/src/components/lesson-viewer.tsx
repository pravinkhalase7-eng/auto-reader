"use client";

import { memo, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { useReaderStore } from "@/store/reader-store";
import type { LessonContent, Paragraph } from "@/types";

const WordSpan = memo(function WordSpan({
  id,
  text,
  isActive,
}: {
  id: string;
  text: string;
  isActive: boolean;
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
        "inline-block rounded-md px-0.5 transition-all duration-150",
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
}: {
  paragraph: Paragraph;
  activeWordId: string | null;
}) {
  return (
    <p
      data-paragraph-id={paragraph.id}
      className="mb-5 text-lg leading-relaxed text-teal-950 md:text-xl md:leading-8"
    >
      {paragraph.sentences.map((sentence) => (
        <span key={sentence.id} data-sentence-id={sentence.id}>
          {sentence.words.map((word) => (
            <WordSpan
              key={word.id}
              id={word.id}
              text={word.text}
              isActive={activeWordId === word.id}
            />
          ))}
        </span>
      ))}
    </p>
  );
}

export function LessonViewer({ content }: { content: LessonContent }) {
  const activeWordId = useReaderStore((s) => s.activeWordId);

  return (
    <article className="prose-lesson max-w-none" aria-live="polite">
      {content.sections.map((section) => (
        <section key={section.id} className="mb-8">
          {section.heading ? (
            <h2 className="font-display mb-4 text-2xl font-bold text-teal-950 md:text-3xl">
              {section.heading}
            </h2>
          ) : null}
          {section.paragraphs.map((p) => (
            <ParagraphBlock key={p.id} paragraph={p} activeWordId={activeWordId} />
          ))}
        </section>
      ))}
    </article>
  );
}
