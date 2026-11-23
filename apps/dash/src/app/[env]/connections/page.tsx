import type { Metadata } from "next";
import { Suspense } from "react";
import { ConnectionsView } from "@/components/views/connections";

export const metadata: Metadata = { title: "Connections" };

export default function Page() {
	return (
		<Suspense>
			<ConnectionsView />
		</Suspense>
	);
}
