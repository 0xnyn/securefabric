import type { Metadata } from "next";
import { Suspense } from "react";
import { StatusView } from "@/components/views/status";

export const metadata: Metadata = { title: "Status" };

export default function Page() {
	return (
		<Suspense>
			<StatusView />
		</Suspense>
	);
}
