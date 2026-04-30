import { useState } from "react";

import { useApp } from "../store";
import { DownloadCsvButton } from "./DownloadCsvButton";
import { FieldsPane } from "./FieldsPane";
import { PdfPane } from "./PdfPane";
import { SelectionPopover } from "./SelectionPopover";

interface PendingSelection {
  text: string;
  rect: DOMRect;
}

interface Props {
  showNewDocument?: boolean;
  showReExtract?: boolean;
  showProvider?: boolean;
}

export function Workspace({
  showNewDocument = true,
  showReExtract = true,
  showProvider = true,
}: Props) {
  const [selection, setSelection] = useState<PendingSelection | null>(null);
  const selectedProvider = useApp((s) => s.selectedProvider);
  const reset = useApp((s) => s.reset);

  return (
    <div className="workspace">
      <header className="workspace-header">
        <span className="workspace-title">Extract</span>
        <span className="workspace-meta">
          {showProvider && (
            <span className="workspace-provider">
              Model<strong>{selectedProvider ?? "default"}</strong>
            </span>
          )}
          <DownloadCsvButton />
          {showNewDocument && (
            <button className="link" onClick={reset}>New document</button>
          )}
        </span>
      </header>
      <div className="workspace-body">
        <PdfPane onSelectText={setSelection} />
        <FieldsPane showReExtract={showReExtract} />
      </div>
      {selection && (
        <SelectionPopover
          text={selection.text}
          rect={selection.rect}
          onClose={() => setSelection(null)}
        />
      )}
    </div>
  );
}
