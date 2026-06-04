import { describe, expect, it, vi } from "vitest";

import { createOverlayHost } from "./overlay-host";

describe("content overlay host", () => {
  it("mounts into a Shadow DOM host without touching the page DOM tree", () => {
    const shadowRoot = { appendChild: vi.fn() };
    const host = {
      id: "",
      attachShadow: vi.fn(() => shadowRoot),
    };
    const documentLike = {
      body: {
        appendChild: vi.fn(),
      },
      createElement: vi.fn(() => host),
      getElementById: vi.fn(() => null),
    };

    const result = createOverlayHost(documentLike);

    expect(documentLike.createElement).toHaveBeenCalledWith("div");
    expect(host.id).toBe("alphaedge-mirror-root");
    expect(host.attachShadow).toHaveBeenCalledWith({ mode: "open" });
    expect(documentLike.body.appendChild).toHaveBeenCalledWith(host);
    expect(result.shadowRoot).toBe(shadowRoot);
  });
});
