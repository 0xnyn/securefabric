import type { Metadata } from "next";
import { Suspense } from "react";
import { OverviewView } from "@/components/views/overview";

export const metadata: Metadata = { title: "Overview" };

export default function Page() {
	return (
		<Suspense>
			<OverviewView />
		</Suspense>
	);
}
