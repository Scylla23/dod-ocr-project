import { useEffect, useRef, useState } from "react";

import { Demo } from "./components/Demo";
import { Upload } from "./components/Upload";
import { Workspace } from "./components/Workspace";
import { useApp } from "./store";

function currentPath(): string {
  return typeof window === "undefined" ? "/" : window.location.pathname;
}

export function App() {
  const session = useApp((s) => s.session);
  const reset = useApp((s) => s.reset);
  const [path, setPath] = useState<string>(currentPath());
  const prevPath = useRef<string>(path);

  useEffect(() => {
    const onNav = () => setPath(currentPath());
    window.addEventListener("popstate", onNav);
    return () => window.removeEventListener("popstate", onNav);
  }, []);

  useEffect(() => {
    if (prevPath.current !== path) {
      // crossed route boundaries — drop any session from the previous route
      if (session) reset();
      prevPath.current = path;
    }
  }, [path, session, reset]);

  if (path === "/demo") return <Demo />;
  return session ? <Workspace /> : <Upload />;
}
