import type { Metadata } from "next";
import { Suspense } from "react";
import { OrganizationsView } from "@/components/views/organizations";

export const metadata: Metadata = { title: "Organizations" };

export default function Page() {
	return (
		<Suspense>
			<OrganizationsView />
		</Suspense>
	);
}
