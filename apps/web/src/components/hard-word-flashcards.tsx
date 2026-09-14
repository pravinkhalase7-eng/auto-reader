"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import type { HardWordExplain, TeachLanguage } from "@/types";
import { cn } from "@/lib/utils";

type Props = {
  words: HardWordExplain[];
  language: TeachLanguage;
  onClose?: () => void;
};

export function HardWordFlashcards({ words, language, onClose }: Props) {
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [known, setKnown] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    setIndex(0);
    setFlipped(false);
    setKnown(new Set());
  }, [words]);

  if (!words.length) {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-3 text-sm text-amber-950">
        No hard words for this story yet. Play Learn in Hindi or Learn in Marathi first.
      </div>
    );
  }

  const safeIndex = Math.min(index, words.length - 1);
  const card = words[safeIndex];
  const title = language === "mr" ? "कठीण शब्द — Flashcards" : "मुश्किल शब्द — Flashcards";
  const done = known.size >= words.length;

  return (
    <div className="rounded-2xl border border-violet-200 bg-violet-50/80 p-3 text-sm text-violet-950">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold">{title}</p>
          <p className="mt-0.5 text-xs text-violet-900/70">
            Tap the card to flip. Mark words you know — practice the rest again.
          </p>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full px-3 py-2 text-sm font-semibold text-violet-800 hover:bg-violet-100"
          >
            Close
          </button>
        ) : null}
      </div>

      {done ? (
        <div className="mt-3 space-y-2">
          <p className="font-medium">Great job — you reviewed all {words.length} hard words!</p>
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => {
              setKnown(new Set());
              setIndex(0);
              setFlipped(false);
            }}
          >
            Practice again
          </Button>
        </div>
      ) : (
        <>
          <p className="mt-2 text-xs font-medium text-violet-900/70">
            Card {safeIndex + 1} of {words.length} · Known {known.size}
          </p>
          <button
            type="button"
            onClick={() => setFlipped((v) => !v)}
            className={cn(
              "mt-2 flex min-h-[120px] w-full flex-col items-center justify-center rounded-2xl border-2 border-violet-300 bg-white px-4 py-6 text-center shadow-sm transition",
              flipped ? "border-violet-500 bg-violet-100/60" : "hover:border-violet-400",
            )}
          >
            {!flipped ? (
              <>
                <span className="text-xs uppercase tracking-wide text-violet-700/70">English word</span>
                <span className="mt-2 text-3xl font-bold text-violet-950">{card.word}</span>
                <span className="mt-3 text-xs text-violet-800/60">Tap to see meaning</span>
              </>
            ) : (
              <>
                <span className="text-xs uppercase tracking-wide text-violet-700/70">Meaning</span>
                <span className="mt-2 break-words text-lg font-semibold leading-snug text-violet-950">
                  {card.meaning_hi}
                </span>
                <span className="mt-3 text-xs text-violet-800/60">{card.word}</span>
              </>
            )}
          </button>

          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              className="flex-1"
              onClick={() => {
                setFlipped(false);
                setIndex((i) => (i + 1) % words.length);
              }}
            >
              Next
            </Button>
            <Button
              type="button"
              className="flex-1 bg-violet-700 hover:bg-violet-800"
              onClick={() => {
                const nextKnown = new Set(known);
                nextKnown.add(card.word.toLowerCase());
                setKnown(nextKnown);
                setFlipped(false);
                const remaining = words
                  .map((w, i) => ({ w, i }))
                  .filter(({ w }) => !nextKnown.has(w.word.toLowerCase()));
                if (!remaining.length) return;
                const next = remaining.find(({ i }) => i > safeIndex) || remaining[0];
                setIndex(next.i);
              }}
            >
              I know this
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
