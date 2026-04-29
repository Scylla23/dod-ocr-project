import { beforeEach, describe, expect, it } from "vitest";

import { useApp } from "./store";
import type { SessionData } from "./types";

const sample: SessionData = {
  session_id: "abc",
  page_count: 1,
  schema: [
    { name: "title", type: "string", removable: false },
    { name: "references", type: "list[string]", removable: true },
  ],
  values: { title: "Original", references: ["A", "B"] },
  original_extracted: { title: "OrigClaude", references: ["A"] },
  extraction_errors: [],
};

describe("store", () => {
  beforeEach(() => useApp.getState().reset());

  it("setSession initializes", () => {
    useApp.getState().setSession(sample);
    expect(useApp.getState().session?.session_id).toBe("abc");
    expect(useApp.getState().currentPage).toBe(1);
  });

  it("setFieldValue updates scalar", () => {
    useApp.getState().setSession(sample);
    useApp.getState().setFieldValue("title", "Edited");
    expect(useApp.getState().session?.values.title).toBe("Edited");
  });

  it("appendFieldValue appends and dedupes", () => {
    useApp.getState().setSession(sample);
    useApp.getState().appendFieldValue("references", "C");
    expect(useApp.getState().session?.values.references).toEqual(["A", "B", "C"]);
    useApp.getState().appendFieldValue("references", "A");
    expect(useApp.getState().session?.values.references).toEqual(["A", "B", "C"]);
  });

  it("removeFieldValue drops by index", () => {
    useApp.getState().setSession(sample);
    useApp.getState().removeFieldValue("references", 0);
    expect(useApp.getState().session?.values.references).toEqual(["B"]);
  });

  it("revertField restores scalar to original", () => {
    useApp.getState().setSession(sample);
    useApp.getState().setFieldValue("title", "Mine");
    useApp.getState().revertField("title");
    expect(useApp.getState().session?.values.title).toBe("OrigClaude");
  });

  it("revertField on field with no original uses empty default", () => {
    useApp.getState().setSession(sample);
    useApp.getState().addField({ name: "keywords", type: "string", removable: true });
    useApp.getState().setFieldValue("keywords", "x");
    useApp.getState().revertField("keywords");
    expect(useApp.getState().session?.values.keywords).toBe("");
  });

  it("setSelectedProvider updates state", () => {
    useApp.getState().setSelectedProvider("openai");
    expect(useApp.getState().selectedProvider).toBe("openai");
    useApp.getState().setSelectedProvider(null);
    expect(useApp.getState().selectedProvider).toBeNull();
  });
});
