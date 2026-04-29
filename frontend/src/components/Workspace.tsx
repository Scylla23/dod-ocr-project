import { useState } from "react";

import { FieldsPane } from "./FieldsPane";
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
      <FieldsPane />
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
