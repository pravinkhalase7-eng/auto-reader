"use client";

import { create } from "zustand";
import type { PlaybackStyle, ReadingMode, SpeedOption } from "@/types";

type ReaderState = {
  mode: ReadingMode;
  speed: SpeedOption;
  playbackStyle: PlaybackStyle;
  volume: number;
  isPlaying: boolean;
  activeWordId: string | null;
  activeParagraphId: string | null;
  activeSentenceId: string | null;
  paragraphIndex: number;
  setMode: (mode: ReadingMode) => void;
  setSpeed: (speed: SpeedOption) => void;
  setPlaybackStyle: (style: PlaybackStyle) => void;
  setVolume: (volume: number) => void;
  setPlaying: (playing: boolean) => void;
  setActive: (wordId: string | null, sentenceId?: string | null, paragraphId?: string | null) => void;
  setParagraphIndex: (index: number) => void;
  reset: () => void;
};

export const useReaderStore = create<ReaderState>((set) => ({
  mode: "listen_read",
  speed: "normal",
  playbackStyle: "natural",
  volume: 1,
  isPlaying: false,
  activeWordId: null,
  activeParagraphId: null,
  activeSentenceId: null,
  paragraphIndex: 0,
  setMode: (mode) => set({ mode }),
  setSpeed: (speed) => set({ speed }),
  setPlaybackStyle: (playbackStyle) => set({ playbackStyle }),
  setVolume: (volume) => set({ volume }),
  setPlaying: (isPlaying) => set({ isPlaying }),
  setActive: (activeWordId, activeSentenceId = null, activeParagraphId = null) =>
    set({ activeWordId, activeSentenceId, activeParagraphId }),
  setParagraphIndex: (paragraphIndex) => set({ paragraphIndex }),
  reset: () =>
    set({
      isPlaying: false,
      activeWordId: null,
      activeSentenceId: null,
      activeParagraphId: null,
      paragraphIndex: 0,
    }),
}));
