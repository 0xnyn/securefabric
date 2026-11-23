import type { Metadata } from "next";
import { Suspense } from "react";
import { MetricsView } from "@/components/views/metrics";

export const metadata: Metadata = { title: "Metrics" };

export default function Page() {
	return (
		<Suspense>
			<MetricsView />
		</Suspense>
	);
}
