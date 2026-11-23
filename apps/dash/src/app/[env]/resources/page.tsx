import type { Metadata } from "next";
import { Suspense } from "react";
import { ResourcesView } from "@/components/views/explorers";

export const metadata: Metadata = { title: "Resources" };

export default function Page() {
	return (
		<Suspense>
			<ResourcesView />
		</Suspense>
	);
}
