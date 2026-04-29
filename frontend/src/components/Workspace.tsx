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

export function Workspace() {
  const [selection, setSelection] = useState<PendingSelection | null>(null);
  const selectedProvider = useApp((s) => s.selectedProvider);
  const reset = useApp((s) => s.reset);

  return (
    <div className="workspace">
      <header className="workspace-header">
        <span className="workspace-title">Extract</span>
        <span className="workspace-meta">
          <span className="workspace-provider">
            Model<strong>{selectedProvider ?? "default"}</strong>
          </span>
          <DownloadCsvButton />
          <button className="link" onClick={reset}>New document</button>
        </span>
      </header>
      <div className="workspace-body">
        <PdfPane onSelectText={setSelection} />
        <FieldsPane />
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
