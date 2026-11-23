import type { Metadata } from "next";
import { Suspense } from "react";
import { FindingsView } from "@/components/views/explorers";

export const metadata: Metadata = { title: "Findings" };

export default function Page() {
	return (
		<Suspense>
			<FindingsView />
		</Suspense>
	);
}
