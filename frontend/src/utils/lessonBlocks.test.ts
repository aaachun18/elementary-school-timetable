import { describe, expect, it } from "vitest";
import {
  blockGroupKey,
  blockGroupMemberIds,
  buildBlockLinks,
  type BlockLesson,
} from "./lessonBlocks";

function lesson(
  scheduleId: number,
  weekday: number,
  period: number,
  block: { requirementId?: number; no: number; seq: number; size: number } | null = null,
): BlockLesson {
  return {
    scheduleId,
    requirementId: block?.requirementId ?? 40,
    blockNo: block?.no ?? null,
    blockSeq: block?.seq ?? null,
    blockSize: block?.size ?? 0,
    weekday,
    period,
  };
}

// Science "2+1": block 1 on Monday 1-2, block 2 on Tuesday 1; English (no
// pattern) on Monday 3.
const s1 = lesson(1, 1, 1, { no: 1, seq: 1, size: 2 });
const s2 = lesson(2, 1, 2, { no: 1, seq: 2, size: 2 });
const s3 = lesson(3, 2, 1, { no: 2, seq: 1, size: 1 });
const e1 = lesson(4, 1, 3, null);
const schedules = [s1, s2, s3, e1];

describe("blockGroupKey / blockGroupMemberIds", () => {
  it("groups the lessons of one block of two or more", () => {
    expect(blockGroupKey(s1)).toBe("40:1");
    expect([...blockGroupMemberIds(schedules, s2)].sort()).toEqual([1, 2]);
  });

  it("leaves a lesson in no block, or in a block of one, on its own", () => {
    expect(blockGroupKey(e1)).toBeNull();
    expect(blockGroupKey(s3)).toBeNull();
    expect([...blockGroupMemberIds(schedules, e1)]).toEqual([4]);
    expect([...blockGroupMemberIds(schedules, s3)]).toEqual([3]);
  });

  it("does not mix blocks of different requirements", () => {
    const other = lesson(9, 3, 1, { requirementId: 41, no: 1, seq: 1, size: 2 });
    expect([...blockGroupMemberIds([...schedules, other], s1)].sort()).toEqual([1, 2]);
  });
});

describe("buildBlockLinks", () => {
  it("joins adjacent lessons of a block, top to bottom", () => {
    const links = buildBlockLinks(schedules);
    expect(links.get(1)).toEqual({ above: false, below: true });
    expect(links.get(2)).toEqual({ above: true, below: false });
    // Single lessons get no bar.
    expect(links.has(3)).toBe(false);
    expect(links.has(4)).toBe(false);
  });

  it("marks a split block's lessons without joining them", () => {
    const split = [s1, { ...s2, weekday: 3 }];
    const links = buildBlockLinks(split);
    expect(links.get(1)).toEqual({ above: false, below: false });
    expect(links.get(2)).toEqual({ above: false, below: false });
  });

  it("does not join lessons in reverse order", () => {
    const reversed = [{ ...s1, period: 2 }, { ...s2, period: 1 }];
    const links = buildBlockLinks(reversed);
    expect(links.get(1)).toEqual({ above: false, below: false });
  });

  it("joins every lesson of a block of three", () => {
    const triple = [1, 2, 3].map((seq) => lesson(seq, 4, seq + 4, { no: 1, seq, size: 3 }));
    const links = buildBlockLinks(triple);
    expect(links.get(2)).toEqual({ above: true, below: true });
    expect(links.get(3)).toEqual({ above: true, below: false });
  });
});
