"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import type { AttemptResult, Quiz } from "@/types";
import { cn } from "@/lib/utils";

export default function QuizPage() {
  const { id } = useParams<{ id: string }>();
  const token = useAuthStore((s) => s.token);
  const router = useRouter();
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [textAnswer, setTextAnswer] = useState("");
  const [answers, setAnswers] = useState<
    Record<string, { selected_option_id?: string; text_answer?: string }>
  >({});
  const [feedback, setFeedback] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  const { data: quiz, isLoading } = useQuery({
    queryKey: ["quiz", id],
    queryFn: () => api<Quiz>(`/lessons/${id}/quiz`),
    enabled: !!token && !!id,
  });

  const question = quiz?.questions[index];
  const progress = quiz ? ((index + 1) / quiz.questions.length) * 100 : 0;

  const isChoice = useMemo(
    () => question && ["mcq", "true_false", "vocabulary", "sequence"].includes(question.question_type),
    [question],
  );

  async function next() {
    if (!question || !quiz) return;
    const payload = isChoice
      ? { selected_option_id: selected || undefined }
      : { text_answer: textAnswer };
    const nextAnswers = { ...answers, [question.id]: payload };
    setAnswers(nextAnswers);
    setFeedback(null);
    setSelected(null);
    setTextAnswer("");

    if (index < quiz.questions.length - 1) {
      setIndex(index + 1);
      return;
    }

    setSubmitting(true);
    try {
      const result = await api<AttemptResult>(`/quizzes/${quiz.id}/attempt`, {
        method: "POST",
        body: JSON.stringify({
          answers: Object.entries(nextAnswers).map(([question_id, a]) => ({
            question_id,
            ...a,
          })),
        }),
      });
      sessionStorage.setItem(`attempt-${id}`, JSON.stringify(result));
      router.push(`/lessons/${id}/result`);
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) return null;

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl">
        <p className="text-sm font-semibold text-teal-800">AI Teacher</p>
        <h1 className="font-display text-3xl font-bold text-teal-950">Let&apos;s see how well you understood!</h1>
        {isLoading || !question || !quiz ? (
          <p className="mt-6">I&apos;m preparing some questions for you...</p>
        ) : (
          <Card className="mt-6">
            <div className="mb-2 flex justify-between text-sm font-semibold text-teal-900/70">
              <span>
                Question {index + 1} of {quiz.questions.length}
              </span>
              <span className="capitalize">{question.question_type.replace("_", " ")}</span>
            </div>
            <ProgressBar value={progress} className="mb-6" />
            <h2 className="font-display text-2xl font-semibold text-teal-950">{question.prompt}</h2>

            {isChoice ? (
              <div className="mt-6 space-y-3">
                {question.options.map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setSelected(opt.id)}
                    className={cn(
                      "flex w-full items-start gap-3 rounded-2xl border-2 px-4 py-3 text-left transition",
                      selected === opt.id
                        ? "border-teal-600 bg-teal-50"
                        : "border-teal-900/10 hover:border-teal-600/40",
                    )}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-900/10 font-bold text-teal-900">
                      {opt.label}
                    </span>
                    <span className="pt-1 text-teal-950">{opt.text}</span>
                  </button>
                ))}
              </div>
            ) : (
              <textarea
                className="mt-6 min-h-[120px] w-full rounded-2xl border border-teal-900/15 p-4"
                placeholder="Type your answer..."
                value={textAnswer}
                onChange={(e) => setTextAnswer(e.target.value)}
              />
            )}

            {feedback ? <p className="mt-4 text-sm font-medium text-teal-800">{feedback}</p> : null}

            <div className="mt-6 flex justify-end">
              <Button
                size="lg"
                disabled={submitting || (isChoice ? !selected : !textAnswer.trim())}
                onClick={next}
              >
                {index === quiz.questions.length - 1
                  ? submitting
                    ? "Checking..."
                    : "Finish"
                  : "Next"}
              </Button>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
