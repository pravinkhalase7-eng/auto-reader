"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export function PaviAvatar({
  listening = false,
  speaking = false,
  size = "md",
}: {
  listening?: boolean;
  speaking?: boolean;
  size?: "sm" | "md" | "lg";
}) {
  const dim = size === "lg" ? "h-24 w-24" : size === "sm" ? "h-8 w-8" : "h-12 w-12";
  const letter = size === "lg" ? "text-3xl" : size === "sm" ? "text-sm" : "text-lg";
  return (
    <div className={cn("relative shrink-0", dim)}>
      {(listening || speaking) && (
        <>
          <motion.span
            className="absolute -inset-2 rounded-full border border-teal-400/40"
            animate={{ scale: [1, 1.12, 1], opacity: [0.5, 0.15, 0.5] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.span
            className="absolute inset-0 rounded-full bg-teal-400/15"
            animate={{ scale: [1, 1.08, 1] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
          />
        </>
      )}
      <div
        className={cn(
          "relative flex h-full w-full items-center justify-center rounded-full bg-[#0f4f4a] text-white shadow-[0_8px_24px_-8px_rgba(15,79,74,0.55)] ring-2 ring-white/70",
        )}
      >
        <span className={cn("font-display font-semibold tracking-tight", letter)}>P</span>
      </div>
    </div>
  );
}
