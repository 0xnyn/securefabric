// Verify a SecureFabric webhook (Node.js 18+, ES module, no dependencies).
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

export function verify(
	secret,
	signatureHeader,
	timestamp,
	rawBody,
	toleranceSeconds = 300
) {
	const ts = Number.parseInt(timestamp, 10);
	if (!Number.isFinite(ts)) {
		return false;
	}
	if (Math.abs(Date.now() / 1000 - ts) > toleranceSeconds) {
		return false; // replay protection
	}
	const expected =
		"v1=" +
		crypto
			.createHmac("sha256", secret)
			.update(Buffer.concat([Buffer.from(`${ts}.`), rawBody]))
			.digest("hex");
	const want = Buffer.from(expected);
	// During a secret rotation two signatures are sent, comma-separated.
	return signatureHeader.split(",").some((part) => {
		const candidate = Buffer.from(part.trim());
		return (
			candidate.length === want.length &&
			crypto.timingSafeEqual(candidate, want)
		);
	});
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
	// node verify.mjs <secret> <SecureFabric-Signature> <SecureFabric-Timestamp> < body
	const chunks = [];
	for await (const chunk of process.stdin) {
		chunks.push(chunk);
	}
	const [secret, header, timestamp] = process.argv.slice(2);
	process.exit(
		verify(secret, header, timestamp, Buffer.concat(chunks)) ? 0 : 1
	);
}
