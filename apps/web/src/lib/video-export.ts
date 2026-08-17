/** Convert a recorded WebM (or other) blob to MP4 in the browser. */

let ffmpegSingleton: import("@ffmpeg/ffmpeg").FFmpeg | null = null;
let loadPromise: Promise<import("@ffmpeg/ffmpeg").FFmpeg> | null = null;

async function getFfmpeg(): Promise<import("@ffmpeg/ffmpeg").FFmpeg> {
  if (ffmpegSingleton?.loaded) return ffmpegSingleton;
  if (loadPromise) return loadPromise;

  loadPromise = (async () => {
    const { FFmpeg } = await import("@ffmpeg/ffmpeg");
    const { toBlobURL } = await import("@ffmpeg/util");
    const ffmpeg = new FFmpeg();
    // Single-thread core — no COOP/COEP headers required (keeps API image loads working).
    const base = "https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.10/dist/esm";
    await ffmpeg.load({
      coreURL: await toBlobURL(`${base}/ffmpeg-core.js`, "text/javascript"),
      wasmURL: await toBlobURL(`${base}/ffmpeg-core.wasm`, "application/wasm"),
    });
    ffmpegSingleton = ffmpeg;
    return ffmpeg;
  })();

  try {
    return await loadPromise;
  } catch (err) {
    loadPromise = null;
    throw err;
  }
}

export function looksLikeMp4(blob: Blob, mimeHint = ""): boolean {
  const mime = (blob.type || mimeHint).toLowerCase();
  return mime.includes("mp4") || mime.includes("avc1") || mime.includes("mpeg4");
}

/**
 * Remux/transcode to H.264 + AAC MP4 for widest player support (phones, WhatsApp, etc.).
 */
export async function convertVideoToMp4(
  input: Blob,
  opts?: {
    onProgress?: (ratio: number) => void;
    isCancelled?: () => boolean;
  },
): Promise<{ blob: Blob; converted: boolean }> {
  if (looksLikeMp4(input)) {
    opts?.onProgress?.(1);
    return { blob: input, converted: true };
  }

  const { fetchFile } = await import("@ffmpeg/util");
  const ffmpeg = await getFfmpeg();
  if (opts?.isCancelled?.()) throw new Error("cancelled");

  const onProgress = ({ progress }: { progress: number }) => {
    opts?.onProgress?.(Math.min(1, Math.max(0, progress)));
  };
  ffmpeg.on("progress", onProgress);

  const inName = "story-in.webm";
  const outName = "story-out.mp4";
  try {
    await ffmpeg.writeFile(inName, await fetchFile(input));
    if (opts?.isCancelled?.()) throw new Error("cancelled");

    const code = await ffmpeg.exec([
      "-i",
      inName,
      "-c:v",
      "libx264",
      "-preset",
      "ultrafast",
      "-pix_fmt",
      "yuv420p",
      "-c:a",
      "aac",
      "-b:a",
      "128k",
      "-movflags",
      "+faststart",
      outName,
    ]);
    if (code !== 0) {
      throw new Error(`ffmpeg exited with ${code}`);
    }
    if (opts?.isCancelled?.()) throw new Error("cancelled");

    const data = await ffmpeg.readFile(outName);
    const bytes = data instanceof Uint8Array ? data : new TextEncoder().encode(String(data));
    const copy = new Uint8Array(bytes.byteLength);
    copy.set(bytes);
    opts?.onProgress?.(1);
    return { blob: new Blob([copy], { type: "video/mp4" }), converted: true };
  } finally {
    ffmpeg.off("progress", onProgress);
    try {
      await ffmpeg.deleteFile(inName);
    } catch {
      /* ignore */
    }
    try {
      await ffmpeg.deleteFile(outName);
    } catch {
      /* ignore */
    }
  }
}
