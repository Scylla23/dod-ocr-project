import type { FieldDef, FieldValue } from "./types";

export function toCsv(
  schema: FieldDef[],
  values: Record<string, FieldValue>,
): string {
  const rows: string[][] = [["field", "value"]];
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
    rows.push([f.name, cell]);
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
