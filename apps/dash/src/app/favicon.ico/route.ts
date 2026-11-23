/**
 * Browsers and crawlers still ask for /favicon.ico directly. Without this the
 * [env] route would answer it with a page; serve the SecureFabric mark (the same
 * as app/icon.svg) instead.
 */
const ICON = `<svg	aria-label="SecureFabric"	fill="none"	height="32"	role="img"	viewBox="0 0 24 24"	width="32"	xmlns="http://www.w3.org/2000/svg">	<rect fill="#533AFD" height="24" rx="5.28" width="24" />	<path		d="M12 5.1L4 18.9H8.53L14.27 9.01ZM16.53 12.92H12L15.47 18.9H20Z"		fill="#ffffff"		fill-opacity="0.92"		transform="translate(0.84 0.84) scale(0.93)"	/></svg>`;

export function GET(): Response {
	return new Response(ICON, {
		headers: {
			"cache-control": "public, max-age=86400",
			"content-type": "image/svg+xml",
		},
	});
}
