import type { Metadata } from "next";
import { Suspense } from "react";
import { WebhooksView } from "@/components/views/webhooks";

export const metadata: Metadata = { title: "Webhooks" };

export default function Page() {
	return (
		<Suspense>
			<WebhooksView />
		</Suspense>
	);
}
