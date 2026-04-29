import type { FieldDef, PatchOp, ProvidersResponse, SessionData } from "./types";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getProviders: async (): Promise<ProvidersResponse> =>
    jsonOrThrow(await fetch("/providers")),
  upload: async (file: File, provider?: string): Promise<SessionData> => {
    const fd = new FormData();
    fd.append("file", file);
    if (provider) fd.append("provider", provider);
    return jsonOrThrow(await fetch("/upload", { method: "POST", body: fd }));
  },
  pdfUrl: (sid: string) => `/sessions/${sid}/pdf`,
  patchValues: async (sid: string, op: PatchOp): Promise<{ field: string; value: unknown }> =>
    jsonOrThrow(
      await fetch(`/sessions/${sid}/values`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(op),
      }),
    ),
  addField: async (sid: string, name: string): Promise<{ schema: FieldDef[] }> =>
    jsonOrThrow(
      await fetch(`/sessions/${sid}/fields`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      }),
    ),
  deleteField: async (sid: string, name: string): Promise<{ schema: FieldDef[] }> =>
    jsonOrThrow(
      await fetch(`/sessions/${sid}/fields/${encodeURIComponent(name)}`, {
        method: "DELETE",
      }),
    ),
  extractPage: async (
    sid: string,
    page: number,
    provider?: string,
  ): Promise<{ values: Record<string, unknown> }> =>
    jsonOrThrow(
      await fetch(`/sessions/${sid}/extract-page`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(provider ? { page, provider } : { page }),
      }),
    ),
  pageTextLength: async (sid: string, page: number): Promise<{ length: number }> =>
    jsonOrThrow(await fetch(`/sessions/${sid}/page/${page}/text-length`)),
};
