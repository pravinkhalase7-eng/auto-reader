"use client";

import { Loader2, Mic, MicOff } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MicState } from "@/lib/speech-providers";
import { PaviVoiceWave } from "@/components/pavi/PaviVoiceWave";

export function PaviMicButton({
  state,
  onClick,
  disabled,
}: {
  state: MicState;
  onClick: () => void;
  disabled?: boolean;
}) {
  const listening = state === "listening";
  const processing = state === "processing" || state === "requesting_permission";
  const errored = state === "error";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || processing}
      aria-label={listening ? "Stop listening" : "Press and speak"}
      className={cn(
        "relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition",
        listening
          ? "bg-[#0f4f4a] text-white"
          : errored
            ? "bg-rose-50 text-rose-700"
            : "bg-teal-50 text-teal-800 hover:bg-teal-100",
        disabled && "opacity-50",
      )}
    >
      {processing ? (
        <Loader2 className="h-5 w-5 animate-spin" />
      ) : errored ? (
        <MicOff className="h-5 w-5" />
      ) : listening ? (
        <PaviVoiceWave active />
      ) : (
        <Mic className="h-5 w-5" />
      )}
    </button>
  );
}
