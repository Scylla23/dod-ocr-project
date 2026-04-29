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

const PAGE_WIDTH = 700;

export function PdfPane({ onSelectText }: Props) {
  const session = useApp((s) => s.session)!;
  const currentPage = useApp((s) => s.currentPage);
  const setPage = useApp((s) => s.setPage);
  const highlightedField = useApp((s) => s.highlightedField);
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRef = useRef<HTMLDivElement>(null);
  const [textLengthHint, setTextLengthHint] = useState<number | null>(null);
  const [pageDims, setPageDims] = useState<{ width: number; height: number } | null>(null);

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

  // Scroll the highlight into view when it changes pages or fires.
  useEffect(() => {
    if (!highlightedField) return;
    const cit = session.citations?.[highlightedField];
    if (!cit || cit.page !== currentPage) return;
    const el = pageRef.current?.querySelector<HTMLElement>(".highlight-rect");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightedField, session.citations, currentPage]);

  const activeCitation =
    highlightedField && session.citations?.[highlightedField]?.page === currentPage
      ? session.citations[highlightedField]
      : null;

  return (
    <div className="pdf-pane">
      <div className="pager">
        <button
          aria-label="previous page"
          disabled={currentPage <= 1}
          onClick={() => setPage(currentPage - 1)}
        >
          ←
        </button>
        <span className="pager-count">
          Folio <span className="pager-folio">{currentPage}</span> / {session.page_count}
        </span>
        <span className="pager-divider" aria-hidden />
        <button
          aria-label="next page"
          disabled={currentPage >= session.page_count}
          onClick={() => setPage(currentPage + 1)}
        >
          →
        </button>
      </div>
      {textLengthHint !== null && textLengthHint < 20 && (
        <div className="hint">This page has little or no selectable text.</div>
      )}
      <div className="pdf-canvas" ref={containerRef} onMouseUp={handleMouseUp}>
        <div className="pdf-page-wrap" ref={pageRef}>
          <Document file={api.pdfUrl(session.session_id)}>
            <Page
              pageNumber={currentPage}
              width={PAGE_WIDTH}
              renderAnnotationLayer={false}
              onRenderSuccess={({ width, height }) => setPageDims({ width, height })}
            />
          </Document>
          {activeCitation && pageDims && (
            <div
              className="highlight-overlay"
              style={{ width: pageDims.width, height: pageDims.height }}
              aria-hidden
            >
              {activeCitation.rects.map(([x, y, w, h], i) => (
                <div
                  key={i}
                  className="highlight-rect"
                  style={{
                    left: `${x * 100}%`,
                    top: `${y * 100}%`,
                    width: `${w * 100}%`,
                    height: `${h * 100}%`,
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
