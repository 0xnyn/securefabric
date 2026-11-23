import type { Metadata } from "next";
import { Suspense } from "react";
import { PlaygroundView } from "@/components/views/playground";

export const metadata: Metadata = { title: "Request console" };

export default function Page() {
	return (
		<Suspense>
			<PlaygroundView />
		</Suspense>
	);
}
