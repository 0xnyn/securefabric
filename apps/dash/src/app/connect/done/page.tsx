import type { Metadata } from "next";
import { Suspense } from "react";
import { ConnectDone } from "@/components/connect/connect-flow";

export const metadata: Metadata = {
	robots: { follow: false, index: false },
	title: "Connected",
};

export default function Page() {
	return (
		<Suspense>
			<ConnectDone />
		</Suspense>
	);
}
