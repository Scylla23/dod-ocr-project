import type {
  Citation,
  FieldDef,
  FieldValue,
  PatchOp,
  ProvidersResponse,
  SessionData,
} from "./types";

export const API_BASE = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/api`;

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getProviders: async (): Promise<ProvidersResponse> =>
    jsonOrThrow(await fetch(`${API_BASE}/providers`)),
  loadDemo: async (): Promise<SessionData> =>
    jsonOrThrow(await fetch(`${API_BASE}/demo/session`, { method: "POST" })),
  upload: async (file: File, provider?: string): Promise<SessionData> => {
    const fd = new FormData();
    fd.append("file", file);
    if (provider) fd.append("provider", provider);
    return jsonOrThrow(await fetch(`${API_BASE}/upload`, { method: "POST", body: fd }));
  },
  pdfUrl: (sid: string) => `${API_BASE}/sessions/${sid}/pdf`,
  patchValues: async (sid: string, op: PatchOp): Promise<{ field: string; value: unknown }> =>
    jsonOrThrow(
      await fetch(`${API_BASE}/sessions/${sid}/values`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(op),
      }),
    ),
  addField: async (sid: string, name: string): Promise<{ schema: FieldDef[] }> =>
    jsonOrThrow(
      await fetch(`${API_BASE}/sessions/${sid}/fields`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      }),
    ),
  deleteField: async (sid: string, name: string): Promise<{ schema: FieldDef[] }> =>
    jsonOrThrow(
      await fetch(`${API_BASE}/sessions/${sid}/fields/${encodeURIComponent(name)}`, {
        method: "DELETE",
      }),
    ),
  extractPage: async (
    sid: string,
    page: number,
    provider?: string,
  ): Promise<{ values: Record<string, unknown> }> =>
    jsonOrThrow(
      await fetch(`${API_BASE}/sessions/${sid}/extract-page`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(provider ? { page, provider } : { page }),
      }),
    ),
  pageTextLength: async (sid: string, page: number): Promise<{ length: number }> =>
    jsonOrThrow(await fetch(`${API_BASE}/sessions/${sid}/page/${page}/text-length`)),
};

export interface StreamHandlers {
  onField?: (name: string, value: FieldValue) => void;
  onCitations?: (citations: Record<string, Citation>) => void;
  onConfidences?: (cs: Record<string, number>) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
}

/**
 * Open an SSE stream for incremental extraction. Returns a function that
 * closes the stream early (e.g. on unmount).
 */
export function streamExtractPage(
  sid: string,
  page: number,
  provider: string | undefined,
  handlers: StreamHandlers,
): () => void {
  const params = new URLSearchParams({ page: String(page) });
  if (provider) params.set("provider", provider);
  const url = `${API_BASE}/sessions/${sid}/extract-page/stream?${params.toString()}`;
  const es = new EventSource(url);

  const safeJson = <T>(raw: string): T | null => {
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  };

  es.addEventListener("field", (e) => {
    const ev = e as MessageEvent<string>;
    const data = safeJson<{ name: string; value: FieldValue }>(ev.data);
    if (data) handlers.onField?.(data.name, data.value);
  });

  es.addEventListener("citations", (e) => {
    const ev = e as MessageEvent<string>;
    const data = safeJson<Record<string, Citation>>(ev.data);
    if (data) handlers.onCitations?.(data);
  });

  es.addEventListener("confidences", (e) => {
    const ev = e as MessageEvent<string>;
    const data = safeJson<Record<string, number>>(ev.data);
    if (data) handlers.onConfidences?.(data);
  });

  es.addEventListener("done", () => {
    handlers.onDone?.();
    es.close();
  });

  es.addEventListener("error", (e) => {
    // SSE 'error' events fire both for our app-level error frame AND for
    // generic transport errors. Only treat the framed event (which has data)
    // as an app error; transport errors after `done` get ignored.
    const ev = e as MessageEvent<string>;
    if (typeof ev.data === "string") {
      const data = safeJson<{ message: string }>(ev.data);
      handlers.onError?.(data?.message ?? "stream error");
    } else if (es.readyState === EventSource.CLOSED) {
      // already closed by us; ignore
    } else {
      handlers.onError?.("connection lost");
    }
    es.close();
  });

  return () => es.close();
}
