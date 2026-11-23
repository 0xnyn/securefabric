import type { Metadata } from "next";
import { Suspense } from "react";
import { AdminView } from "@/components/views/admin";

export const metadata: Metadata = { title: "Operator console" };

export default function Page() {
	return (
		<Suspense>
			<AdminView />
		</Suspense>
	);
}
