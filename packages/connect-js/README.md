# @securefabric/connect-js

Open SecureFabric's hosted connect flow on your page so a customer can connect
their security tools without credentials ever touching your frontend.

1. Your backend creates a session: `POST /v1/connect_sessions` with
   `{ "organization_id": "…", "integrations": ["GITHUB"] }`. It returns `url`
   (single use, valid 30 minutes).
2. Your page opens it:

```ts
import { SecureFabric } from "@securefabric/connect-js";

SecureFabric.connect({
  url: session.url,
  onSuccess: ({ connectionId }) => {/* store it */},
  onError: ({ code, message }) => {/* show it */},
  onClose: () => {/* refresh */},
}).open();
```

React:

```tsx
import { ConnectButton, useSecureFabricConnect } from "@securefabric/connect-js/react";

<ConnectButton url={session.url} onSuccess={({ connectionId }) => save(connectionId)}>
  Connect your tools
</ConnectButton>;
```

- `mode: "modal"` (default) renders a sandboxed iframe over the page; Escape,
  the close button or clicking the backdrop closes it. `mode: "popup"` runs the
  flow in a window instead (for browsers that block cookies in third-party
  frames).
- Messages are accepted only from the connect link's origin **and** from the
  frame (or popup) this call opened. Anything else is ignored.
- Vendor redirect steps (installing the GitHub App) open in a popup from inside
  the frame and report back automatically.
- `onClose` fires exactly once however the flow ends.
