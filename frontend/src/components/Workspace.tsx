import { useState } from "react";

import { PdfPane } from "./PdfPane";

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
        <p className="placeholder">Fields panel — populated in Task 13.</p>
        {selection && (
          <p className="placeholder">
            Selection captured: "{selection.text.slice(0, 40)}…" (popover in Task 13)
          </p>
        )}
      </div>
    </div>
  );
}
