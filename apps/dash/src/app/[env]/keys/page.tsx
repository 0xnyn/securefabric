import type { Metadata } from "next";
import { Suspense } from "react";
import { KeysView } from "@/components/views/keys";

export const metadata: Metadata = { title: "Keys" };

export default function Page() {
	return (
		<Suspense>
			<KeysView />
		</Suspense>
	);
}
