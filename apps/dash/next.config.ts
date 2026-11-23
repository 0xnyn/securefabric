import type { NextConfig } from "next";

const nextConfig: NextConfig = {
	// The dashboard must not be framed; the hosted connect flow is framed by
	// connect-js on customer sites (part 8, section 5).
	headers: async () => [
		{
			headers: [
				{ key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
				{ key: "X-Frame-Options", value: "DENY" },
				{ key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
			],
			source: "/((?!connect).*)",
		},
		{
			headers: [
				{ key: "Content-Security-Policy", value: "frame-ancestors *" },
				{ key: "Referrer-Policy", value: "no-referrer" },
			],
			source: "/connect/:path*",
		},
		{
			headers: [
				{ key: "Content-Security-Policy", value: "frame-ancestors *" },
				{ key: "Referrer-Policy", value: "no-referrer" },
			],
			source: "/connect",
		},
	],
	reactCompiler: true,
};

export default nextConfig;
