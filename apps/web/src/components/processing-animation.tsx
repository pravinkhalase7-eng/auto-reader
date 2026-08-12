"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Sparkles } from "lucide-react";
import { ProgressBar } from "@/components/ui/progress-bar";

const PHOTO_STEPS = [
  { key: "uploaded", label: "I've got your story!" },
  { key: "ocr", label: "I'm reading your textbook pages..." },
  { key: "understanding", label: "I'm understanding the content..." },
  { key: "language", label: "I'm detecting the language..." },
  { key: "preparing_lesson", label: "I'm preparing your lesson..." },
  { key: "preparing_teacher", label: "I'm preparing your AI Teacher..." },
  { key: "illustrating", label: "I'm drawing the story pictures..." },
  { key: "completed", label: "Your lesson is ready!" },
];

const TEXT_STEPS = [
  { key: "uploaded", label: "I've got your story!" },
  { key: "understanding", label: "I'm understanding the story..." },
  { key: "language", label: "I'm detecting the language..." },
  { key: "preparing_lesson", label: "I'm preparing your lesson..." },
  { key: "preparing_teacher", label: "I'm preparing your AI Teacher..." },
  { key: "illustrating", label: "I'm drawing the story pictures..." },
  { key: "completed", label: "Your lesson is ready!" },
];

export function ProcessingAnimation({
  currentStep,
  progress,
  message,
  source = "photos",
}: {
  currentStep: string;
  progress: number;
  message: string;
  source?: "photos" | "text";
}) {
  const steps = source === "text" ? TEXT_STEPS : PHOTO_STEPS;
  const currentIdx = Math.max(
    0,
    steps.findIndex((s) => s.key === currentStep),
  );

  return (
    <div className="mx-auto max-w-lg rounded-[2rem] border border-teal-900/10 bg-white/90 p-8 text-center shadow-xl">
      <motion.div
        animate={{ rotate: [0, 8, -8, 0] }}
        transition={{ repeat: Infinity, duration: 3 }}
        className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-amber-700"
      >
        <Sparkles className="h-8 w-8" />
      </motion.div>
      <h2 className="font-display text-2xl font-bold text-teal-950">Your AI Teacher is working</h2>
      <p className="mt-2 text-teal-900/70">{message}</p>
      <div className="mt-6">
        <ProgressBar value={progress} label="Lesson preparation" />
      </div>
      <ul className="mt-6 space-y-3 text-left">
        {steps.map((step, i) => {
          const done = i < currentIdx || currentStep === "completed";
          const active = i === currentIdx && currentStep !== "completed";
          return (
            <li
              key={step.key}
              className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm ${
                active ? "bg-teal-50 font-semibold text-teal-900" : "text-teal-900/60"
              }`}
            >
              <CheckCircle2 className={`h-5 w-5 ${done || active ? "text-teal-600" : "text-teal-900/20"}`} />
              {step.label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
