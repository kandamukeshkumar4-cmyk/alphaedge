import { FormEvent, useEffect, useState } from "react";

import { getSettings, normalizeApiBase, saveSettings } from "../storage";

type Notice = {
  tone: "success" | "error" | "muted";
  text: string;
};

export function Popup() {
  const [apiBase, setApiBase] = useState("http://localhost:8000");
  const [token, setToken] = useState("");
  const [notice, setNotice] = useState<Notice>({
    tone: "muted",
    text: "Research and paper simulation only.",
  });
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    void getSettings().then((settings) => {
      setApiBase(settings.apiBase);
      setToken(settings.token);
    });
  }, []);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await saveSettings({ apiBase: normalizeApiBase(apiBase), token: token.trim() });
    setNotice({ tone: "success", text: "Settings saved." });
  }

  async function handleCreateProfile() {
    setIsCreating(true);
    try {
      const normalizedApiBase = normalizeApiBase(apiBase);
      const response = await fetch(`${normalizedApiBase}/api/v1/forecasters/anonymous`, {
        method: "POST",
      });
      const data = (await response.json()) as { token?: string; detail?: string };
      if (!response.ok || !data.token) {
        throw new Error(data.detail ?? "Could not create profile.");
      }
      setToken(data.token);
      await saveSettings({ apiBase: normalizedApiBase, token: data.token });
      setNotice({ tone: "success", text: "Forecaster profile created." });
    } catch (error) {
      setNotice({
        tone: "error",
        text: error instanceof Error ? error.message : "Could not create profile.",
      });
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <main className="popup">
      <style>{styles}</style>
      <header>
        <h1>AlphaEdge Mirror</h1>
        <p>Research and paper simulation only. No betting execution or real-money flows.</p>
      </header>

      <form onSubmit={handleSave}>
        <label>
          <span>API Base</span>
          <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} />
        </label>
        <label>
          <span>Forecaster Token</span>
          <input
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
          />
        </label>
        <button type="submit">Save</button>
      </form>

      <button disabled={isCreating} type="button" onClick={() => void handleCreateProfile()}>
        {isCreating ? "Creating" : "Create anonymous profile"}
      </button>

      <div className={`notice ${notice.tone}`}>{notice.text}</div>
    </main>
  );
}

const styles = `
  body { margin: 0; background: #090c0f; }
  .popup {
    box-sizing: border-box;
    width: 320px;
    padding: 16px;
    color: #f2f7f3;
    font: 500 13px/1.4 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  h1 { margin: 0; font-size: 18px; line-height: 1.2; }
  p { margin: 6px 0 14px; color: #9ea9a3; }
  form { display: grid; gap: 10px; margin-bottom: 10px; }
  label { display: grid; gap: 5px; color: #66716b; font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
  input {
    min-height: 34px;
    box-sizing: border-box;
    width: 100%;
    border: 1px solid #243039;
    border-radius: 6px;
    background: #0f1417;
    color: #f2f7f3;
    padding: 6px 8px;
  }
  button {
    min-height: 36px;
    width: 100%;
    border: 1px solid #24c66d;
    border-radius: 6px;
    background: #24c66d;
    color: #090c0f;
    font-weight: 900;
  }
  button + button { margin-top: 8px; }
  button:disabled { opacity: .55; }
  .notice { margin-top: 10px; border-radius: 6px; padding: 8px; font-size: 12px; }
  .muted { background: #151b20; color: #9ea9a3; }
  .success { background: #0c2618; color: #24c66d; }
  .error { background: #2b1012; color: #ff6b6d; }
`;
