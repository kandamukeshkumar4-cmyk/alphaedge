type OverlayHostElement = {
  id: string;
  shadowRoot?: unknown;
  attachShadow: (init: ShadowRootInit) => unknown;
};

export type OverlayDocument = {
  body: { appendChild: (node: unknown) => unknown };
  createElement: (tagName: "div") => OverlayHostElement;
  getElementById: (id: string) => OverlayHostElement | null;
};

export function createOverlayHost(documentRef: OverlayDocument = document as unknown as OverlayDocument) {
  const existing = documentRef.getElementById("alphaedge-mirror-root");
  if (existing?.shadowRoot) {
    return { host: existing, shadowRoot: existing.shadowRoot };
  }

  const host = documentRef.createElement("div");
  host.id = "alphaedge-mirror-root";
  const shadowRoot = host.attachShadow({ mode: "open" });
  documentRef.body.appendChild(host);
  return { host, shadowRoot };
}
