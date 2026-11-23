import type { Metadata } from "next";
import { IntegrationView } from "@/components/views/integrations";

export const metadata: Metadata = { title: "Integration" };

export default async function Page({
	params,
}: {
	params: Promise<{ id: string }>;
}) {
	const { id } = await params;
	return <IntegrationView id={id} />;
}
