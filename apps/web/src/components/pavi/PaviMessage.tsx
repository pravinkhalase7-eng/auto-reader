"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { PaviAvatar } from "@/components/pavi/PaviAvatar";

export function PaviMessage({
  role,
  content,
}: {
  role: string;
  content: string;
}) {
  const mine = role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22 }}
      className={cn("flex items-end gap-2", mine ? "justify-end" : "justify-start")}
    >
      {!mine && <PaviAvatar size="sm" />}
      <div
        className={cn(
          "max-w-[82%] whitespace-pre-wrap px-4 py-3 text-[15px] leading-relaxed md:max-w-[68%]",
          mine
            ? "rounded-[22px] rounded-br-md bg-[#0f4f4a] text-white"
            : "rounded-[22px] rounded-bl-md bg-[#f4f7f5] text-teal-950",
        )}
      >
        {content}
      </div>
    </motion.div>
  );
}
