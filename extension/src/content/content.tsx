import { createRoot } from "react-dom/client";

import { MirrorOverlay } from "./overlay";
import { createOverlayHost, type OverlayDocument } from "./overlay-host";
import { parseSupportedUrl } from "../platforms";

const parsed = parseSupportedUrl(window.location.href, document.title);

if (parsed) {
  const { shadowRoot } = createOverlayHost(document as unknown as OverlayDocument);
  const mount = document.createElement("div");
  (shadowRoot as ShadowRoot).appendChild(mount);
  createRoot(mount).render(<MirrorOverlay market={parsed} />);
}
