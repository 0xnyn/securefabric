# Receiving webhooks

SecureFabric sends events (connection created, sync completed, health changed, actions
completed, …) to HTTPS endpoints you register with `POST /v1/webhook_endpoints`. Every
delivery is signed; verify it before trusting the body.

## The request

| Header | Value |
|---|---|
| `SecureFabric-Event-Id` | `evt_…`, stable across retries (deduplicate on it) |
| `SecureFabric-Event-Type` | e.g. `sync.completed` |
| `SecureFabric-Delivery-Id` | this delivery's id |
| `SecureFabric-Timestamp` | Unix seconds when this attempt was signed |
| `SecureFabric-Signature` | `v1=<hex>`; two of them, comma-separated, for 24 h after a secret rotation |

The body is the event envelope: `{id, type, created_at, environment_id, organization_id,
connection_id, sequence, data}`. `sequence` increases strictly per connection.

## Verifying

The signature is HMAC-SHA256, keyed with the endpoint's secret (shown once at creation and
on rotation), over the string `"{timestamp}.{raw body}"`:

1. Read the **raw** request body, before any JSON parsing.
2. Reject timestamps more than 5 minutes from now (replay protection).
3. Compute `v1=` + hex(HMAC-SHA256(secret, timestamp + "." + body)).
4. Compare in constant time against each comma-separated value of the signature header.

Respond 2xx within 15 seconds. 5xx, 408, 429 and network errors are retried at 10 s, 1 m,
5 m, 30 m, 2 h, 6 h, 12 h and 24 h (with jitter); other 4xx are not. An endpoint failing for
5 days is disabled; re-enable it and replay what you missed with
`POST /v1/webhook_endpoints/{id}/replay`. Events are also available to pull from
`GET /v1/events`.

These samples are the files in [`docs/webhooks/`](../webhooks/). CI runs each one against
signatures produced by the delivery code (valid, rotated, tampered, wrong secret, stale), so
they stay correct.

### Python

```python
import hashlib, hmac, time

def verify(secret: str, signature_header: str, timestamp: str, raw_body: bytes,
           tolerance_s: int = 300) -> bool:
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > tolerance_s:
        return False
    expected = "v1=" + hmac.new(secret.encode(), f"{ts}.".encode() + raw_body,
                                hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, p.strip()) for p in signature_header.split(","))
```

### Node.js

```js
import crypto from "node:crypto";

export function verify(secret, signatureHeader, timestamp, rawBody, toleranceSeconds = 300) {
  const ts = Number.parseInt(timestamp, 10);
  if (!Number.isFinite(ts)) return false;
  if (Math.abs(Date.now() / 1000 - ts) > toleranceSeconds) return false;
  const want = Buffer.from(
    "v1=" + crypto.createHmac("sha256", secret)
      .update(Buffer.concat([Buffer.from(`${ts}.`), rawBody])).digest("hex"),
  );
  return signatureHeader.split(",").some((part) => {
    const candidate = Buffer.from(part.trim());
    return candidate.length === want.length && crypto.timingSafeEqual(candidate, want);
  });
}
```

With Express, read the raw body: `express.raw({ type: "application/json" })`.

### Go

```go
func Verify(secret, signatureHeader, timestamp string, rawBody []byte, tolerance time.Duration) bool {
	ts, err := strconv.ParseInt(timestamp, 10, 64)
	if err != nil {
		return false
	}
	if math.Abs(float64(time.Now().Unix()-ts)) > tolerance.Seconds() {
		return false
	}
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(strconv.FormatInt(ts, 10) + "."))
	mac.Write(rawBody)
	expected := "v1=" + hex.EncodeToString(mac.Sum(nil))
	for _, part := range strings.Split(signatureHeader, ",") {
		if hmac.Equal([]byte(strings.TrimSpace(part)), []byte(expected)) {
			return true
		}
	}
	return false
}
```

### Ruby

```ruby
require "openssl"

def verify(secret, signature_header, timestamp, raw_body, tolerance_seconds = 300)
  ts = begin
    Integer(timestamp)
  rescue ArgumentError, TypeError
    return false
  end
  return false if (Time.now.to_i - ts).abs > tolerance_seconds

  expected = "v1=" + OpenSSL::HMAC.hexdigest("SHA256", secret, "#{ts}." + raw_body)
  signature_header.split(",").any? { |part| secure_compare(part.strip, expected) }
end
```

(`secure_compare` is a constant-time comparison; see `verify.rb`. On Ruby 2.7+ you can use
`OpenSSL.fixed_length_secure_compare` after checking lengths.)

## Rotating the secret

`POST /v1/webhook_endpoints/{id}/rotate_secret` returns the new secret once. For the next 24
hours each delivery carries both signatures, so deploy the new secret at your pace; the
verifiers above accept either.
