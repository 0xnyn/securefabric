import type { Metadata } from "next";
import { Suspense } from "react";
import { LogsView } from "@/components/views/logs/logs-view";

export const metadata: Metadata = { title: "Logs" };

export default function Page() {
	return (
		<Suspense>
			<LogsView />
		</Suspense>
	);
}
