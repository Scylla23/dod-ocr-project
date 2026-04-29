import { useState } from "react";

const DEMO_PASSWORD = "bravent2026";

interface Props {
  onUnlock: () => void;
}

export function DemoGate({ onUnlock }: Props) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password === DEMO_PASSWORD) {
      sessionStorage.setItem("demo_auth", "1");
      onUnlock();
    } else {
      setError("Incorrect password");
    }
  }

  return (
    <div className="upload">
      <section className="upload-stage">
        <div className="upload-lede">
          <p className="kicker">Restricted</p>
          <h1>
            Enter the<br /> password <em>to</em><br /> view the demo.
          </h1>
          <p className="lead">
            The pre-extracted demo is gated. Ask the team for the passphrase
            if you need access.
          </p>
        </div>

        <div className="upload-panel">
          <form className="demo-gate-form" onSubmit={handleSubmit}>
            <label className="demo-gate-label">
              Password
              <input
                type="password"
                value={password}
                autoFocus
                onChange={(e) => {
                  setPassword(e.target.value);
                  setError(null);
                }}
              />
            </label>
            <button type="submit" className="demo-gate-submit">
              Unlock demo
            </button>
            {error && <p className="error">{error}</p>}
          </form>
        </div>
      </section>
    </div>
  );
}
