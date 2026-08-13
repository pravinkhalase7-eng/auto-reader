import { describe, expect, it } from "vitest";
import { pickVoice, scoreVoice, voicesForLanguage } from "@/lib/speech";

function fakeVoice(name: string, lang: string): SpeechSynthesisVoice {
  return {
    name,
    lang,
    localService: false,
    default: false,
    voiceURI: `${lang}:${name}`,
  };
}

describe("Marathi voice picking", () => {
  const hindi = fakeVoice("Google हिन्दी", "hi-IN");
  const english = fakeVoice("Google US English", "en-US");
  const marathi = fakeVoice("Google मराठी", "mr-IN");

  it("does not score Hindi as a Marathi voice", () => {
    expect(scoreVoice(hindi, ["mr-IN", "mr"])).toBe(0);
  });

  it("does not list Hindi when asking for Marathi", () => {
    expect(voicesForLanguage("mr", [hindi, english])).toEqual([]);
    expect(voicesForLanguage("mr", [hindi, marathi]).map((v) => v.lang)).toEqual(["mr-IN"]);
  });

  it("does not stand Hindi in when the device has no Marathi voice", () => {
    const picked = pickVoice("mr", [hindi, english]);
    expect(picked.voice).toBeNull();
    expect(picked.warning).toMatch(/cloud voice/i);
    expect(picked.warning).not.toMatch(/Hindi is standing in/i);
  });
});
