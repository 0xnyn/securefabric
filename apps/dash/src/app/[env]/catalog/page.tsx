import type { Metadata } from "next";
import { Suspense } from "react";
import { CatalogView } from "@/components/views/catalog";

export const metadata: Metadata = { title: "Catalog" };

export default function Page() {
	return (
		<Suspense>
			<CatalogView />
		</Suspense>
	);
}
