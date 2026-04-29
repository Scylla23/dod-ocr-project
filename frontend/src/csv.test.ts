import { describe, expect, it } from "vitest";

import { toCsv } from "./csv";
import type { FieldDef } from "./types";

const schema: FieldDef[] = [
  { name: "title", type: "string", removable: false },
  { name: "references", type: "list[string]", removable: true },
];

describe("toCsv", () => {
  it("emits header plus one row per field", () => {
    const csv = toCsv(schema, { title: "Hello", references: ["A", "B"] });
    expect(csv).toBe(
      '"field","value"\r\n' +
      '"title","Hello"\r\n' +
      '"references","A; B"',
    );
  });

  it("treats missing values as empty cells", () => {
    const csv = toCsv(schema, {});
    expect(csv).toBe(
      '"field","value"\r\n' +
      '"title",""\r\n' +
      '"references",""',
    );
  });

  it("escapes quotes by doubling them", () => {
    const csv = toCsv(
      [{ name: "quote", type: "string", removable: false }],
      { quote: 'She said "hi"' },
    );
    expect(csv).toBe(
      '"field","value"\r\n' +
      '"quote","She said ""hi"""',
    );
  });

  it("preserves commas and newlines inside quoted cells", () => {
    const csv = toCsv(
      [{ name: "note", type: "string", removable: false }],
      { note: "a, b\nc" },
    );
    expect(csv).toBe(
      '"field","value"\r\n' +
      '"note","a, b\nc"',
    );
  });

  it("joins list items with '; '", () => {
    const csv = toCsv(
      [{ name: "tags", type: "list[string]", removable: true }],
      { tags: ["x", "y", "z"] },
    );
    expect(csv).toBe(
      '"field","value"\r\n' +
      '"tags","x; y; z"',
    );
  });
});
