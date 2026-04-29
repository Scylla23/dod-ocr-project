import { useState } from "react";

import { PdfPane } from "./PdfPane";
import { SelectionPopover } from "./SelectionPopover";

interface PendingSelection {
  text: string;
  rect: DOMRect;
}

export function Workspace() {
  const [selection, setSelection] = useState<PendingSelection | null>(null);

  return (
    <div className="workspace">
      <PdfPane onSelectText={setSelection} />
      <div className="fields-pane">
        <p className="placeholder">Fields panel — populated in Task 14.</p>
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
