"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, BookOpenCheck, Headphones, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

const steps = [
  { title: "Upload", desc: "Snap a textbook page" },
  { title: "Understand", desc: "AI Teacher reads it" },
  { title: "Listen", desc: "Words light up as you hear" },
  { title: "Quiz", desc: "Practice in your language" },
];

export default function LandingPage() {
  return (
    <div className="overflow-hidden">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5">
        <div className="font-display text-2xl font-bold text-teal-950">AI Teacher</div>
        <div className="flex gap-2">
          <Button asChild variant="ghost">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild>
            <Link href="/register">Start Learning</Link>
          </Button>
        </div>
      </header>

      <section className="relative mx-auto grid max-w-6xl items-center gap-10 px-4 pb-16 pt-8 md:grid-cols-2 md:pt-16">
        <div>
          <motion.p
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-3 inline-flex items-center gap-2 rounded-full bg-teal-900/10 px-3 py-1 text-sm font-semibold text-teal-800"
          >
            <Sparkles className="h-4 w-4" /> For every lesson in your bag
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="font-display text-4xl font-bold leading-tight tracking-tight text-teal-950 md:text-6xl"
          >
            Your AI Teacher for Every Lesson
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12 }}
            className="mt-5 max-w-lg text-lg text-teal-900/75"
          >
            Upload a page from your textbook. Read it, listen to it, understand it, and test yourself.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.18 }}
            className="mt-8 flex flex-wrap gap-3"
          >
            <Button asChild size="lg">
              <Link href="/register">
                Start Learning <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/login">Try a Demo</Link>
            </Button>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1, duration: 0.5 }}
          className="relative rounded-[2rem] border border-teal-900/10 bg-white/80 p-6 shadow-2xl"
        >
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-100 text-amber-700">
              <Headphones className="h-6 w-6" />
            </div>
            <div>
              <p className="font-semibold text-teal-950">AI Teacher</p>
              <p className="text-sm text-teal-800/70">Let&apos;s read this together!</p>
            </div>
          </div>
          <div className="rounded-2xl bg-teal-50 p-5 text-lg leading-relaxed text-teal-950">
            The <span className="rounded-md bg-amber-300 px-1 font-semibold">lion</span> was sleeping in the forest...
          </div>
          <div className="mt-4 grid grid-cols-4 gap-2">
            {steps.map((s, i) => (
              <motion.div
                key={s.title}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 + i * 0.08 }}
                className="rounded-xl bg-gradient-to-b from-white to-teal-50 p-3 text-center"
              >
                <p className="text-xs font-bold text-teal-900">{s.title}</p>
                <p className="mt-1 text-[10px] text-teal-800/70">{s.desc}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-20">
        <div className="grid gap-4 md:grid-cols-3">
          {[
            {
              icon: BookOpenCheck,
              title: "English, Hindi & Marathi",
              body: "Questions and narration match your lesson language.",
            },
            {
              icon: Headphones,
              title: "Word-by-word highlighting",
              body: "Follow along as your AI Teacher reads aloud.",
            },
            {
              icon: Sparkles,
              title: "Friendly quizzes",
              body: "Practice what you read — with kind feedback, never shame.",
            },
          ].map((f) => (
            <div key={f.title} className="rounded-3xl border border-teal-900/10 bg-white/70 p-6">
              <f.icon className="mb-3 h-7 w-7 text-teal-700" />
              <h3 className="font-display text-xl font-semibold text-teal-950">{f.title}</h3>
              <p className="mt-2 text-sm text-teal-900/70">{f.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
