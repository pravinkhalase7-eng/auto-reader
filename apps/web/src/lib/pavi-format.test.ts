import { describe, expect, it } from "vitest";
import { BrowserSpeechProvider } from "@/lib/speech-providers";
import { isFailedStatus, statusLabel } from "@/lib/pavi-format";

describe("pavi format", () => {
  it("labels reminder and call statuses", () => {
    expect(statusLabel("scheduled")).toBe("Scheduled");
    expect(statusLabel("completed")).toBe("Completed");
    expect(isFailedStatus("failed")).toBe(true);
    expect(isFailedStatus("scheduled")).toBe(false);
  });
});

describe("browser speech provider", () => {
  it("reports unsupported without Web Speech API", () => {
    const provider = new BrowserSpeechProvider();
    expect(provider.isSupported()).toBe(false);
    expect(provider.name).toBe("browser");
  });
});
