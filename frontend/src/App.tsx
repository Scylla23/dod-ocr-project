import { Upload } from "./components/Upload";
import { Workspace } from "./components/Workspace";
import { useApp } from "./store";

export function App() {
  const session = useApp((s) => s.session);
  return session ? <Workspace /> : <Upload />;
}
