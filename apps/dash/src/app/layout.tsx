import type { Metadata } from "next";
import { Inter } from "next/font/google";

import "../index.css";
import { Providers } from "@/components/shell/providers";

// The design tokens read Inter from --font-inter (packages/tokens/DESIGN.md).
const inter = Inter({
	subsets: ["latin"],
	variable: "--font-inter",
});

/** Absolute URLs for the share image: the deployment on Vercel, else local. */
function siteUrl(): URL {
	const host =
		process.env.VERCEL_PROJECT_PRODUCTION_URL ?? process.env.VERCEL_URL;
	return new URL(
		host ? `https://${host}` : `http://localhost:${process.env.PORT ?? 3000}`
	);
}

export const metadata: Metadata = {
	description:
		"Try the SecureFabric unified API for security tools: browse the catalog, connect sandbox accounts, and read normalized vulnerabilities, devices and identities.",
	metadataBase: siteUrl(),
	title: {
		default: "SecureFabric",
		template: "%s · SecureFabric",
	},
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html lang="en" suppressHydrationWarning>
			<body className={`${inter.variable} antialiased`}>
				<Providers>{children}</Providers>
			</body>
		</html>
	);
}
