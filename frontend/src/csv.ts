import type { FieldDef, FieldValue } from "./types";

export function toCsv(
  schema: FieldDef[],
  values: Record<string, FieldValue>,
  confidences?: Record<string, number>,
): string {
  const rows: string[][] = [["field", "value", "confidence"]];
  for (const f of schema) {
    const raw = values[f.name];
    let cell: string;
    if (Array.isArray(raw)) {
      cell = raw.join("; ");
    } else if (raw == null) {
      cell = "";
    } else {
      cell = String(raw);
    }
    const conf = confidences?.[f.name];
    const confCell = conf !== undefined && conf > 0 ? `${Math.round(conf * 100)}%` : "";
    rows.push([f.name, cell, confCell]);
  }
  return rows.map((r) => r.map(quote).join(",")).join("\r\n");
}

function quote(s: string): string {
  return `"${s.replace(/"/g, '""')}"`;
}

export function downloadCsv(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
