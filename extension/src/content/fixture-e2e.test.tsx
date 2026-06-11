// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import corpus from "../../fixtures/platform-pages.json";
import { sendForecastToBackend } from "../backend-client";
import { idempotencyKeyFor } from "../queue";
import { parseSupportedUrl } from "../platforms";
import { prefillForMarket } from "../prefill";
import { isLockForecastMessage, type LockForecastMessage } from "../messaging";
import { createOverlayHost, type OverlayDocument } from "./overlay-host";
import { MirrorOverlay } from "./overlay";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

type PlatformName = "polymarket" | "kalshi" | "fanduel";
type Fixture = {
  url: string;
  title: string;
  expectedExternalId: string;
  manualOnly: boolean;
  html: string;
};

// FanDuel deferred: extension no longer matches FanDuel pages; skip those fixtures.
const ACTIVE_PLATFORMS: PlatformName[] = ["polymarket", "kalshi"];

const fixtures = ACTIVE_PLATFORMS.flatMap(
  (platform) =>
    (corpus[platform] as Fixture[]).map((fixture, index) => ({
      platform,
      fixture,
      name: `${platform} #${index + 1}`,
    })),
);

describe("fixture-page overlay E2E", () => {
  let root: Root | null = null;
  let lockMessages: LockForecastMessage[] = [];

  beforeEach(() => {
    lockMessages = [];
    vi.stubGlobal("chrome", chromeMock(lockMessages));
  });

  afterEach(() => {
    act(() => {
      root?.unmount();
    });
    root = null;
    vi.unstubAllGlobals();
    document.body.innerHTML = "";
  });

  it("capture card exposes a probability slider and a Lock forecast button", async () => {
    const polyFixtures = corpus["polymarket"] as Fixture[];
    const fixture = polyFixtures[0];
    document.body.innerHTML = fixture.html;
    document.title = fixture.title;
    const market = parseSupportedUrl(fixture.url, fixture.title)!;

    const prefill = await prefillForMarket({
      apiBase: "https://api.example.test",
      market,
      pageTitle: fixture.title,
      fetcher: async () => resolveResponse("polymarket", fixture),
    });
    const overlayHost = createOverlayHost(document as unknown as OverlayDocument);
    const shadowRoot = overlayHost.shadowRoot as ShadowRoot;
    const mount = document.createElement("div");
    shadowRoot.appendChild(mount);

    await act(async () => {
      root = createRoot(mount);
      root.render(<MirrorOverlay market={market} prefill={prefill} />);
    });
    await act(flushEffects);

    expect(shadowRoot.querySelector('input[type="range"]')).not.toBeNull();
    const buttons = Array.from(shadowRoot.querySelectorAll("button"));
    const lockButton = buttons.find((b) => /lock forecast/i.test(b.textContent ?? ""));
    expect(lockButton).not.toBeUndefined();
  });

  it("capture card contains no banned execution copy", async () => {
    const polyFixtures = corpus["polymarket"] as Fixture[];
    const fixture = polyFixtures[0];
    document.body.innerHTML = fixture.html;
    document.title = fixture.title;
    const market = parseSupportedUrl(fixture.url, fixture.title)!;

    const prefill = await prefillForMarket({
      apiBase: "https://api.example.test",
      market,
      pageTitle: fixture.title,
      fetcher: async () => resolveResponse("polymarket", fixture),
    });
    const overlayHost = createOverlayHost(document as unknown as OverlayDocument);
    const shadowRoot = overlayHost.shadowRoot as ShadowRoot;
    const mount = document.createElement("div");
    shadowRoot.appendChild(mount);

    await act(async () => {
      root = createRoot(mount);
      root.render(<MirrorOverlay market={market} prefill={prefill} />);
    });
    await act(flushEffects);

    const text = (shadowRoot.textContent ?? "").toLowerCase();
    const BANNED = ["place bet", "auto bet", "guaranteed profit", "wallet", "private key", "real-money"];
    for (const phrase of BANNED) {
      expect(text.includes(phrase), `banned phrase "${phrase}" in overlay`).toBe(false);
    }
  });

  it.each(fixtures)(
    "injects Shadow DOM overlay and sends a backend forecast for $name",
    async ({ platform, fixture }) => {
      document.body.innerHTML = fixture.html;
      document.title = fixture.title;
      const parsed = parseSupportedUrl(fixture.url, fixture.title);
      expect(parsed).not.toBeNull();
      const market = parsed!;

      const prefill = await prefillForMarket({
        apiBase: "https://api.example.test",
        market,
        pageTitle: fixture.title,
        fetcher: async () => resolveResponse(platform, fixture),
      });
      const overlayHost = createOverlayHost(document as unknown as OverlayDocument);
      const shadowRoot = overlayHost.shadowRoot as ShadowRoot;
      const mount = document.createElement("div");
      shadowRoot.appendChild(mount);

      await act(async () => {
        root = createRoot(mount);
        root.render(<MirrorOverlay market={market} prefill={prefill} />);
      });
      await act(flushEffects);

      expect(document.getElementById("alphaedge-mirror-root")?.shadowRoot).toBe(shadowRoot);
      expect(shadowRoot.textContent).toContain("AlphaEdge Mirror");

      await fillAndSubmit(shadowRoot, fixture.manualOnly);

      expect(lockMessages).toHaveLength(1);
      const message = lockMessages[0];
      expect(message.payload).toMatchObject({
        token: "forecaster-token",
        url: market.canonicalUrl,
        user_probability: 0.64,
        outcome_label: "YES",
        source: "extension",
      });
      expect(message.payload.snapshot_metadata.provider).toBe(market.provider);
      if (fixture.manualOnly) {
        expect(message.payload.snapshot_source).toBe("manual");
        expect(message.payload.snapshot_metadata.manual_odds).toBe("+120");
      } else {
        expect(message.payload.snapshot_source).toBe(`${platform}.fixture`);
        expect(message.payload.market_implied_probability).toBe(0.57);
      }

      const backendFetch = vi.fn(async () =>
        new Response(JSON.stringify({ id: "forecast-id" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      );
      const result = await sendForecastToBackend({
        apiBase: "https://api.example.test",
        message,
        idempotencyKey: idempotencyKeyFor(message.payload),
        fetcher: backendFetch,
      });

      expect(result.ok).toBe(true);
      expect(backendFetch).toHaveBeenCalledWith(
        "https://api.example.test/api/v1/forecasts",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(message.payload),
        }),
      );
    },
  );
});

async function fillAndSubmit(shadowRoot: ShadowRoot, manualOnly: boolean) {
  const inputs = Array.from(shadowRoot.querySelectorAll("input"));
  if (manualOnly) {
    await changeInput(inputs[1], "+120");
    await changeInput(inputs[2], "45");
  }
  const range = shadowRoot.querySelector('input[type="range"]') as HTMLInputElement;
  await changeInput(range, "64");
  const form = shadowRoot.querySelector("form") as HTMLFormElement;
  await act(async () => {
    form.dispatchEvent(new SubmitEvent("submit", { bubbles: true, cancelable: true }));
  });
}

async function changeInput(input: HTMLInputElement, value: string) {
  setNativeInputValue(input, value);
  await act(async () => {
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function setNativeInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
}

async function flushEffects() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

function resolveResponse(platform: PlatformName, fixture: Fixture) {
  return new Response(
    JSON.stringify({
      id: `${platform}-market-id`,
      platform: platform === "fanduel" ? "manual" : platform,
      external_id: fixture.expectedExternalId,
      url: fixture.url,
      title: fixture.title,
      category: platform === "fanduel" ? "Manual" : "Fixture",
      status: "open",
      close_at: "2026-06-10T20:00:00Z",
      resolved_at: null,
      snapshot: {
        implied_probability: 0.57,
        source: `${platform}.fixture`,
        metadata: { status: "active" },
      },
    }),
    {
      status: 200,
      headers: { "content-type": "application/json" },
    },
  );
}

function chromeMock(lockMessages: LockForecastMessage[]) {
  return {
    runtime: {
      sendMessage: (message: unknown, callback?: (response: { ok: boolean; data?: unknown }) => void) => {
        if (isLockForecastMessage(message)) {
          lockMessages.push(message);
        }
        callback?.({ ok: true, data: { id: "forecast-id" } });
      },
    },
    storage: {
      local: {
        get: (_keys: unknown, callback: (items: Record<string, unknown>) => void) => {
          callback({
            token: "forecaster-token",
            apiBase: "https://api.example.test",
            dashboardUrl: "https://app.example.test/forecast",
          });
        },
        set: (_items: Record<string, unknown>, callback?: () => void) => callback?.(),
      },
    },
  };
}
