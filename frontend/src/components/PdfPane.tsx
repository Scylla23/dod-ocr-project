import { useEffect, useRef, useState } from "react";
import { Document, Page } from "react-pdf";

import { api } from "../api";
import { useApp } from "../store";

interface SelectionPayload {
  text: string;
  rect: DOMRect;
}

interface Props {
  onSelectText: (payload: SelectionPayload | null) => void;
}

export function PdfPane({ onSelectText }: Props) {
  const session = useApp((s) => s.session)!;
  const currentPage = useApp((s) => s.currentPage);
  const setPage = useApp((s) => s.setPage);
  const containerRef = useRef<HTMLDivElement>(null);
  const [textLengthHint, setTextLengthHint] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.pageTextLength(session.session_id, currentPage).then(({ length }) => {
      if (!cancelled) setTextLengthHint(length);
    });
    return () => {
      cancelled = true;
    };
  }, [session.session_id, currentPage]);

  function handleMouseUp() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) {
      onSelectText(null);
      return;
    }
    const text = sel.toString().trim();
    if (!text) {
      onSelectText(null);
      return;
    }
    const range = sel.getRangeAt(0);
    const container = containerRef.current;
    if (!container || !container.contains(range.commonAncestorContainer)) {
      onSelectText(null);
      return;
    }
    onSelectText({ text, rect: range.getBoundingClientRect() });
  }

  return (
    <div className="pdf-pane">
      <div className="pager">
        <button disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>
          ◀
        </button>
        <span>
          Page {currentPage} / {session.page_count}
        </span>
        <button
          disabled={currentPage >= session.page_count}
          onClick={() => setPage(currentPage + 1)}
        >
          ▶
        </button>
      </div>
      {textLengthHint !== null && textLengthHint < 20 && (
        <div className="hint">This page has little or no selectable text.</div>
      )}
      <div className="pdf-canvas" ref={containerRef} onMouseUp={handleMouseUp}>
        <Document file={api.pdfUrl(session.session_id)}>
          <Page pageNumber={currentPage} width={700} renderAnnotationLayer={false} />
        </Document>
      </div>
    </div>
  );
}
