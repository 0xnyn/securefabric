import type { Metadata } from "next";
import { ConnectorView } from "@/components/views/catalog";

export const metadata: Metadata = { title: "Connector" };

export default async function Page({
	params,
}: {
	params: Promise<{ provider: string }>;
}) {
	const { provider } = await params;
	return <ConnectorView id={provider} />;
}
