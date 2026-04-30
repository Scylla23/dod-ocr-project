import { useEffect, useRef, useState } from "react";

import { Demo } from "./components/Demo";
import { DemoGate } from "./components/DemoGate";
import { Upload } from "./components/Upload";
import { Workspace } from "./components/Workspace";
import { useApp } from "./store";

function currentPath(): string {
  return typeof window === "undefined" ? "/" : window.location.pathname;
}

function readDemoAuth(): boolean {
  return typeof window !== "undefined"
    && window.sessionStorage.getItem("demo_auth") === "1";
}

export function App() {
  const session = useApp((s) => s.session);
  const reset = useApp((s) => s.reset);
  const [path, setPath] = useState<string>(currentPath());
  const [demoAuthed, setDemoAuthed] = useState<boolean>(readDemoAuth());
  const prevPath = useRef<string>(path);

  useEffect(() => {
    const onNav = () => {
      setPath(currentPath());
      setDemoAuthed(readDemoAuth());
    };
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

  if (path.startsWith("/demo/usace-digital-library")) {
    return demoAuthed
      ? <Demo />
      : <DemoGate onUnlock={() => setDemoAuthed(true)} />;
  }
  return session ? <Workspace /> : <Upload />;
}
