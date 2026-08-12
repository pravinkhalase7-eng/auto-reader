"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Pause,
  Play,
  RotateCcw,
  SkipBack,
  SkipForward,
  Volume2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useReaderStore } from "@/store/reader-store";
import type { AudioAsset, LessonContent, PlaybackStyle, SpeedOption } from "@/types";
import { cn } from "@/lib/utils";
import { buildUtterance, SPEED_RATE, waitForVoices } from "@/lib/speech";

type FlatWord = {
  id: string;
  text: string;
  sentenceId: string;
  paragraphId: string;
};

type FlatSentence = {
  id: string;
  paragraphId: string;
  words: FlatWord[];
  text: string;
  ranges: { start: number; end: number; wordOffset: number }[];
  globalStart: number;
};

function flattenContent(content: LessonContent) {
  const words: FlatWord[] = [];
  const sentences: FlatSentence[] = [];
  const paragraphs: { id: string; startWord: number; startSentence: number }[] = [];

  for (const section of content.sections) {
    for (const para of section.paragraphs) {
      const startWord = words.length;
      const startSentence = sentences.length;

      for (const sent of para.sentences) {
        const sentWords: FlatWord[] = [];
        let text = "";
        const ranges: FlatSentence["ranges"] = [];
        const globalStart = words.length;

        sent.words.forEach((w, wordOffset) => {
          if (text.length > 0) text += " ";
          const start = text.length;
          text += w.text;
          const flat = {
            id: w.id,
            text: w.text,
            sentenceId: sent.id,
            paragraphId: para.id,
          };
          sentWords.push(flat);
          words.push(flat);
          ranges.push({ start, end: text.length, wordOffset });
        });

        if (sentWords.length) {
          sentences.push({
            id: sent.id,
            paragraphId: para.id,
            words: sentWords,
            text,
            ranges,
            globalStart,
          });
        }
      }

      paragraphs.push({ id: para.id, startWord, startSentence });
    }
  }

  return { words, sentences, paragraphs };
}

function wordOffsetAtChar(
  ranges: FlatSentence["ranges"],
  charIndex: number,
): number {
  if (!ranges.length) return 0;
  let match = 0;
  for (const r of ranges) {
    if (charIndex >= r.start) match = r.wordOffset;
    if (charIndex >= r.start && charIndex < r.end) return r.wordOffset;
  }
  return match;
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, ms));
}

export function ReadingPlayer({
  content,
}: {
  content: LessonContent;
  audio: AudioAsset | null;
}) {
  const {
    mode,
    speed,
    playbackStyle,
    volume,
    isPlaying,
    paragraphIndex,
    activeWordId,
    setPlaying,
    setActive,
    setSpeed,
    setPlaybackStyle,
    setVolume,
    setParagraphIndex,
    setMode,
    reset,
  } = useReaderStore();

  const { words, sentences, paragraphs } = useMemo(
    () => flattenContent(content),
    [content],
  );

  const [voiceWarning, setVoiceWarning] = useState<string | null>(null);
  const [voicesReady, setVoicesReady] = useState(false);

  const cancelledRef = useRef(false);
  const pausedRef = useRef(false);
  const runIdRef = useRef(0);
  const wordCursorRef = useRef(0);
  const sentenceCursorRef = useRef(0);
  const estimateTimerRef = useRef<number | null>(null);

  useEffect(() => {
    waitForVoices().then(() => setVoicesReady(true));
  }, []);

  const clearEstimate = () => {
    if (estimateTimerRef.current) {
      window.clearInterval(estimateTimerRef.current);
      estimateTimerRef.current = null;
    }
  };

  const activateGlobal = useCallback(
    (index: number) => {
      const w = words[index];
      if (!w) return;
      wordCursorRef.current = index;
      setActive(w.id, w.sentenceId, w.paragraphId);
      const pIdx = paragraphs.findIndex((p) => p.id === w.paragraphId);
      if (pIdx >= 0) setParagraphIndex(pIdx);
    },
    [paragraphs, setActive, setParagraphIndex, words],
  );

  const speakUtterance = useCallback(
    (
      text: string,
      voices: SpeechSynthesisVoice[],
      onBoundary?: (charIndex: number) => void,
    ) =>
      new Promise<"ended" | "error">((resolve) => {
        const { utterance, warning } = buildUtterance(text, {
          language: content.language,
          speed,
          volume,
          voices,
        });
        if (warning) setVoiceWarning(warning);
        utterance.onboundary = (event) => {
          if (event.name && event.name !== "word") return;
          onBoundary?.(event.charIndex);
        };
        utterance.onend = () => resolve("ended");
        utterance.onerror = () => resolve("error");
        window.speechSynthesis.speak(utterance);
      }),
    [content.language, speed, volume],
  );

  /** Fluent playback: whole sentence, highlight via charIndex (or timed estimate). */
  const speakSentenceNatural = useCallback(
    async (sentence: FlatSentence, voices: SpeechSynthesisVoice[], runId: number) => {
      activateGlobal(sentence.globalStart);
      let boundaryHits = 0;

      const msPerWord = Math.max(
        160,
        Math.round(280 / SPEED_RATE[speed]),
      );

      // Soft estimate only until real boundaries arrive
      let est = 0;
      clearEstimate();
      estimateTimerRef.current = window.setInterval(() => {
        if (pausedRef.current || cancelledRef.current || runIdRef.current !== runId) return;
        if (boundaryHits > 0) return;
        if (est < sentence.words.length) {
          activateGlobal(sentence.globalStart + est);
          est += 1;
        }
      }, msPerWord);

      await speakUtterance(sentence.text, voices, (charIndex) => {
        boundaryHits += 1;
        const offset = wordOffsetAtChar(sentence.ranges, charIndex);
        activateGlobal(sentence.globalStart + offset);
      });

      clearEstimate();
      activateGlobal(sentence.globalStart + sentence.words.length - 1);
    },
    [activateGlobal, speakUtterance, speed],
  );

  /** Careful karaoke: one word at a time. */
  const speakSentenceWordByWord = useCallback(
    async (sentence: FlatSentence, voices: SpeechSynthesisVoice[], runId: number) => {
      for (let i = 0; i < sentence.words.length; i++) {
        if (cancelledRef.current || runIdRef.current !== runId) return;
        while (pausedRef.current && !cancelledRef.current && runIdRef.current === runId) {
          await sleep(80);
        }
        if (cancelledRef.current || runIdRef.current !== runId) return;

        activateGlobal(sentence.globalStart + i);
        await speakUtterance(sentence.words[i].text, voices);
        await sleep(content.language === "en" ? 25 : 40);
      }
    },
    [activateGlobal, content.language, speakUtterance],
  );

  const firstSentenceForParagraph = useCallback(
    (pIndex: number) => paragraphs[Math.max(0, Math.min(pIndex, paragraphs.length - 1))]?.startSentence ?? 0,
    [paragraphs],
  );

  const runFromSentence = useCallback(
    async (startSentence: number) => {
      if (typeof window === "undefined" || !window.speechSynthesis) return;
      if (mode === "read") {
        setPlaying(true);
        return;
      }

      const runId = ++runIdRef.current;
      cancelledRef.current = false;
      pausedRef.current = false;
      setPlaying(true);
      window.speechSynthesis.cancel();
      clearEstimate();
      await sleep(30);

      const voices = await waitForVoices();
      const style: PlaybackStyle = playbackStyle;

      for (let i = startSentence; i < sentences.length; i++) {
        if (cancelledRef.current || runIdRef.current !== runId) break;
        while (pausedRef.current && !cancelledRef.current && runIdRef.current === runId) {
          await sleep(80);
        }
        if (cancelledRef.current || runIdRef.current !== runId) break;

        sentenceCursorRef.current = i;
        const sentence = sentences[i];
        const pIdx = paragraphs.findIndex((p) => p.id === sentence.paragraphId);
        if (pIdx >= 0) setParagraphIndex(pIdx);

        if (style === "word") {
          await speakSentenceWordByWord(sentence, voices, runId);
        } else {
          await speakSentenceNatural(sentence, voices, runId);
        }
      }

      if (runIdRef.current === runId) setPlaying(false);
    },
    [
      mode,
      paragraphs,
      playbackStyle,
      sentences,
      setParagraphIndex,
      setPlaying,
      speakSentenceNatural,
      speakSentenceWordByWord,
    ],
  );

  const stopAll = useCallback(() => {
    cancelledRef.current = true;
    pausedRef.current = false;
    runIdRef.current += 1;
    clearEstimate();
    window.speechSynthesis?.cancel();
    setPlaying(false);
  }, [setPlaying]);

  const play = () => {
    void runFromSentence(firstSentenceForParagraph(paragraphIndex));
  };

  const pause = () => {
    pausedRef.current = true;
    clearEstimate();
    window.speechSynthesis?.cancel();
    setPlaying(false);
  };

  const resume = () => {
    pausedRef.current = false;
    void runFromSentence(sentenceCursorRef.current);
  };

  const restart = () => {
    stopAll();
    reset();
    sentenceCursorRef.current = 0;
    wordCursorRef.current = 0;
    window.setTimeout(() => void runFromSentence(0), 60);
  };

  useEffect(() => () => stopAll(), [stopAll]);

  const activeIndex = words.findIndex((w) => w.id === activeWordId);
  const progress =
    words.length === 0 ? 0 : ((Math.max(activeIndex, 0) + 1) / words.length) * 100;

  return (
    <div className="rounded-3xl border border-teal-900/10 bg-white/95 p-4 shadow-lg">
      <div className="mb-3 flex flex-wrap gap-2">
        {(
          [
            ["listen_read", "Listen + Read"],
            ["listen", "Listen"],
            ["read", "Read"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setMode(value)}
            className={cn(
              "rounded-full px-3 py-1.5 text-xs font-semibold",
              mode === value ? "bg-teal-700 text-white" : "bg-teal-50 text-teal-900",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setPlaybackStyle("natural")}
          className={cn(
            "rounded-full px-3 py-1.5 text-xs font-semibold",
            playbackStyle === "natural" ? "bg-amber-500 text-white" : "bg-amber-50 text-amber-950",
          )}
        >
          Normal play
        </button>
        <button
          type="button"
          onClick={() => setPlaybackStyle("word")}
          className={cn(
            "rounded-full px-3 py-1.5 text-xs font-semibold",
            playbackStyle === "word" ? "bg-amber-500 text-white" : "bg-amber-50 text-amber-950",
          )}
        >
          Word by word
        </button>
      </div>

      <div className="mb-3 h-2 overflow-hidden rounded-full bg-teal-900/10">
        <div
          className="h-full bg-teal-600 transition-all duration-150"
          style={{ width: `${Math.max(0, progress)}%` }}
        />
      </div>

      {voiceWarning ? (
        <p className="mb-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-950" role="status">
          {voiceWarning}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-center gap-2">
        <Button
          variant="outline"
          size="icon"
          aria-label="Previous paragraph"
          onClick={() => {
            stopAll();
            const next = Math.max(0, paragraphIndex - 1);
            setParagraphIndex(next);
            sentenceCursorRef.current = firstSentenceForParagraph(next);
          }}
        >
          <SkipBack className="h-4 w-4" />
        </Button>
        {!isPlaying ? (
          <Button
            size="lg"
            aria-label="Play"
            disabled={!voicesReady && mode !== "read"}
            onClick={pausedRef.current ? resume : play}
          >
            <Play className="h-5 w-5" /> Play
          </Button>
        ) : (
          <Button size="lg" variant="secondary" aria-label="Pause" onClick={pause}>
            <Pause className="h-5 w-5" /> Pause
          </Button>
        )}
        <Button variant="outline" size="icon" aria-label="Restart" onClick={restart}>
          <RotateCcw className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          aria-label="Next paragraph"
          onClick={() => {
            stopAll();
            const next = Math.min(paragraphs.length - 1, paragraphIndex + 1);
            setParagraphIndex(next);
            sentenceCursorRef.current = firstSentenceForParagraph(next);
          }}
        >
          <SkipForward className="h-4 w-4" />
        </Button>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
        <label className="flex items-center gap-2 text-teal-900">
          Speed
          <select
            className="rounded-xl border border-teal-900/15 bg-white px-2 py-1"
            value={speed}
            onChange={(e) => setSpeed(e.target.value as SpeedOption)}
            aria-label="Reading speed"
          >
            <option value="very_slow">Very Slow</option>
            <option value="slow">Slow</option>
            <option value="normal">Normal</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-teal-900">
          <Volume2 className="h-4 w-4" />
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
            aria-label="Volume"
          />
        </label>
      </div>
    </div>
  );
}
