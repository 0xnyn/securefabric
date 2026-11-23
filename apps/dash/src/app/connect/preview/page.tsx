import type { Metadata } from "next";
import { ConnectPreview } from "@/components/connect/connect-flow";

export const metadata: Metadata = {
	robots: { follow: false, index: false },
	title: "Connect page preview",
};

export default function Page() {
	return <ConnectPreview />;
}
