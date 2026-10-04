import { describe, expect, it } from "vitest";
import { compact, estimateScanSeconds, formatDuration, parseDate, titleCase } from "./utils";

describe("utils", () => {
  it("formats durations", () => {
    expect(formatDuration(42)).toBe("42s");
    expect(formatDuration(125)).toBe("2m 5s");
    expect(formatDuration(3720)).toBe("1h 2m");
    expect(formatDuration(null)).toBe("—");
  });
  it("treats zone-less ISO strings as UTC", () => {
    expect(parseDate("2026-10-04T05:00:00")?.toISOString()).toBe("2026-10-04T05:00:00.000Z");
    expect(parseDate("2026-10-04T05:00:00+00:00")?.toISOString()).toBe("2026-10-04T05:00:00.000Z");
    expect(parseDate(null)).toBeNull();
  });
  it("title-cases enum names", () => {
    expect(titleCase("AUDIENCE_NETWORK")).toBe("Audience Network");
  });
  it("compacts numbers", () => {
    expect(compact(1200)).toBe("1.2K");
  });
  it("estimates scan time from throughput", () => {
    expect(estimateScanSeconds(300, 300)).toBe(75);
    expect(estimateScanSeconds(150, null)).toBe(75);
  });
});
