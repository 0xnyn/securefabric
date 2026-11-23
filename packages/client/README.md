# @securefabric/client

A typed fetch client for the SecureFabric API, generated from the FastAPI OpenAPI schema.

- `src/v1.ts` is **generated**. Don't edit it: run `make generate` (or `pnpm -F @securefabric/client generate`). It's committed, and `check-generated` fails CI and the git hooks when it drifts from the API.
- `src/index.ts` contains `createClient(baseUrl, { token?, headers?, fetch? })` (openapi-fetch), `unwrap()` (returns typed data or throws `ClientResponseError` subclasses built from RFC 9457 problem details: `{type, title, status, detail, code, request_id, errors[]}`; `.code`, `.requestId`, `.fieldErrors`, `.retryAfter` on 429), `isApiError(e, code?)`, and the type helpers `schemas`, `operations`, `paths`, `RequestBody<OperationId>`.

```ts
import { createClient, unwrap, isApiError } from "@securefabric/client";

const api = createClient("http://localhost:8000");
const org = await unwrap(
  api.POST("/v1/organizations", { body: { identifier: "acme", name: "Acme" } })
);
```

Generation runs `uv run securefabric-openapi | openapi-typescript --enum-values --default-non-nullable=false`. The second flag keeps request fields that have defaults optional. Response fields are required server-side through `ResponseModel`.
