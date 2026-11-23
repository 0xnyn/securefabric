import type { Metadata } from "next";
import { Suspense } from "react";
import { IntegrationsView } from "@/components/views/integrations";

export const metadata: Metadata = { title: "Integrations" };

export default function Page() {
	return (
		<Suspense>
			<IntegrationsView />
		</Suspense>
	);
}
