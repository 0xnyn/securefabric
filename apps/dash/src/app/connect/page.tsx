import type { Metadata } from "next";
import { Suspense } from "react";
import { ConnectFlow } from "@/components/connect/connect-flow";

export const metadata: Metadata = {
	robots: { follow: false, index: false },
	title: "Connect",
};

export default function Page() {
	return (
		<Suspense>
			<ConnectFlow />
		</Suspense>
	);
}
