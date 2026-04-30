import { downloadCsv, toCsv } from "../csv";
import { useApp } from "../store";

export function DownloadCsvButton() {
  const session = useApp((s) => s.session);
  if (!session) return null;

  function handleClick() {
    if (!session) return;
    const csv = toCsv(session.schema, session.values, session.confidences);
    const sid = session.session_id.slice(0, 8);
    downloadCsv(`extraction-${sid}.csv`, csv);
  }

  return (
    <button className="link" onClick={handleClick}>
      Download CSV
    </button>
  );
}
