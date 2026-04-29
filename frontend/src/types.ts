export type FieldType = "string" | "list[string]";

export interface FieldDef {
  name: string;
  type: FieldType;
  removable: boolean;
}

export type FieldValue = string | string[];

export interface Citation {
  page: number; // 1-indexed
  rects: number[][]; // [[x, y, w, h]] in normalized [0,1] page-fraction coords
  quote: string;
}

export interface SessionData {
  session_id: string;
  page_count: number;
  schema: FieldDef[];
  values: Record<string, FieldValue>;
  original_extracted: Record<string, FieldValue>;
  extraction_errors: number[];
  citations: Record<string, Citation>;
}

export type PatchOp =
  | { op: "set"; field: string; value: string }
  | { op: "append"; field: string; value: string }
  | { op: "remove"; field: string; index: number }
  | { op: "revert"; field: string };

export interface ProvidersResponse {
  providers: string[];
  default: string;
}
