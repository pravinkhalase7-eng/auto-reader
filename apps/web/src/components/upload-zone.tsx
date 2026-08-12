"use client";

import { useCallback, useState } from "react";
import { Camera, ChevronDown, ChevronUp, ImagePlus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function UploadZone({
  files,
  onChange,
}: {
  files: File[];
  onChange: (files: File[]) => void;
}) {
  const [dragOver, setDragOver] = useState(false);

  const addFiles = useCallback(
    (list: FileList | File[]) => {
      const next = Array.from(list).filter((f) => f.type.startsWith("image/"));
      onChange([...files, ...next]);
    },
    [files, onChange],
  );

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (e.dataTransfer.files) addFiles(e.dataTransfer.files);
        }}
        className={cn(
          "flex flex-col items-center justify-center rounded-[2rem] border-2 border-dashed px-6 py-14 text-center transition",
          dragOver ? "border-teal-600 bg-teal-50" : "border-teal-900/20 bg-white/70",
        )}
      >
        <ImagePlus className="mb-3 h-10 w-10 text-teal-700" aria-hidden />
        <p className="font-display text-xl font-semibold text-teal-950">Drop textbook photos here</p>
        <p className="mt-1 max-w-md text-sm text-teal-900/70">
          Add every page of the story, in order. I&apos;ll read them as one continuous lesson.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-3">
          <label>
            <input
              type="file"
              accept="image/*"
              multiple
              className="sr-only"
              onChange={(e) => e.target.files && addFiles(e.target.files)}
            />
            <span className="inline-flex h-11 cursor-pointer items-center rounded-2xl bg-teal-700 px-5 text-sm font-semibold text-white hover:bg-teal-800">
              Choose photos
            </span>
          </label>
          <label>
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="sr-only"
              onChange={(e) => e.target.files && addFiles(e.target.files)}
            />
            <span className="inline-flex h-11 cursor-pointer items-center gap-2 rounded-2xl border-2 border-teal-700/20 bg-white px-5 text-sm font-semibold text-teal-900">
              <Camera className="h-4 w-4" /> Camera
            </span>
          </label>
        </div>
      </div>

      {files.length > 0 ? (
        <ul className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
          {files.map((file, i) => (
            <li key={`${file.name}-${i}`} className="relative overflow-hidden rounded-2xl border border-teal-900/10 bg-white">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={URL.createObjectURL(file)}
                alt={`Page ${i + 1}`}
                className="aspect-[3/4] w-full object-cover"
              />
              <div className="absolute left-2 top-2 rounded-full bg-teal-900/80 px-2 py-0.5 text-xs font-semibold text-white">
                Page {i + 1}
              </div>
              <div className="absolute right-2 top-2 flex flex-col gap-1">
                <Button
                  type="button"
                  size="icon"
                  variant="secondary"
                  className="h-8 w-8"
                  aria-label={`Move page ${i + 1} up`}
                  disabled={i === 0}
                  onClick={() => {
                    if (i === 0) return;
                    const next = [...files];
                    [next[i - 1], next[i]] = [next[i], next[i - 1]];
                    onChange(next);
                  }}
                >
                  <ChevronUp className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  size="icon"
                  variant="secondary"
                  className="h-8 w-8"
                  aria-label={`Move page ${i + 1} down`}
                  disabled={i === files.length - 1}
                  onClick={() => {
                    if (i === files.length - 1) return;
                    const next = [...files];
                    [next[i], next[i + 1]] = [next[i + 1], next[i]];
                    onChange(next);
                  }}
                >
                  <ChevronDown className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  size="icon"
                  variant="secondary"
                  className="h-8 w-8"
                  aria-label={`Remove page ${i + 1}`}
                  onClick={() => onChange(files.filter((_, idx) => idx !== i))}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
