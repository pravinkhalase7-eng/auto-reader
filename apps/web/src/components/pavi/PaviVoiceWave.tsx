"use client";

import { cn } from "@/lib/utils";

export function PaviVoiceWave({ active }: { active: boolean }) {
  return (
    <div className="flex h-5 items-end gap-0.5" aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          className={cn("w-0.5 rounded-full bg-white", active ? "pavi-wave" : "h-1.5 opacity-50")}
          style={{ animationDelay: `${i * 0.1}s` }}
        />
      ))}
    </div>
  );
}
