import { Upload } from "./components/Upload";
import { useApp } from "./store";

export function App() {
  const session = useApp((s) => s.session);
  if (!session) return <Upload />;
  return <div className="app">Session loaded: {session.session_id}</div>;
}
