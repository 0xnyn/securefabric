import type { Metadata } from "next";
import { ProviderView } from "@/components/views/provider";

export const metadata: Metadata = { title: "Catalog" };

export default async function Page({
	params,
}: {
	params: Promise<{ provider: string }>;
}) {
	const { provider } = await params;
	return <ProviderView slug={provider} />;
}
