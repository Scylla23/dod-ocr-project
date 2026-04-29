# PDF Extract — Manual Test Checklist

Run after each major change. Backend on `:8000`, frontend on `:5173`.

## Setup
- [ ] Copy `backend/.env.example` to `backend/.env` and fill in real API keys.
- [ ] `cd backend && uvicorn app.main:app --reload --port 8000`
- [ ] `cd frontend && npm run dev`
- [ ] Open http://localhost:5173

## Sample uploads (use `DOD SAFE-8f7gk7Rejn97VEuB/`)
For each PDF:
- [ ] EC 1105-2-2_19720615.pdf — completes ≤30s, `document_number` non-empty
- [ ] EC 1105-2-6_19730309.pdf — completes ≤30s, pagination shows 2 pages
- [ ] ETL 1110-1-153_19930331.pdf — completes ≤30s, `document_number` non-empty
- [ ] ETL 1110-3-407_19891023.pdf — 99 pages, paginate to page 50, sees "no selectable text" hint
- [ ] EM 1110-2-400_19710901.pdf — 43 pages, completes ≤45s

## Interaction (with EC 1105-2-2)
- [ ] On page 1, select "EC 1105-2-2" → popover opens → assign to `document_number`. Value updates.
- [ ] Click "revert" next to `document_number`. Claude's original value returns.
- [ ] Add custom field `keywords` via "+ Create new field…" — assign 3 different selections to `keywords`. Use × to remove the middle one. List shows 2.
- [ ] Delete a USACE extra (e.g. `applicability`) via the row's "delete" link. Field disappears.
- [ ] Confirm `title` has no "delete" link (non-removable).

## Re-extract
- [ ] On EM 1110-2-400 page 3, click "Re-extract page 3". Watch list field `references` grow. Scalar fields previously edited do NOT change.

## State reset
- [ ] Refresh the browser. App returns to upload screen (state lost, expected).
- [ ] Restart backend. Frontend still loaded → next API call returns 404 → app redirects to upload.
