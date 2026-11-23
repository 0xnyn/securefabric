import type { Metadata } from "next";
import { Suspense } from "react";
import { SettingsView } from "@/components/views/settings";

export const metadata: Metadata = { title: "Settings" };

export default function Page() {
	return (
		<Suspense>
			<SettingsView />
		</Suspense>
	);
}
