import type { Metadata } from "next";
import { OrganizationView } from "@/components/views/organizations";

export const metadata: Metadata = { title: "Organization" };

export default async function Page({
	params,
}: {
	params: Promise<{ id: string }>;
}) {
	const { id } = await params;
	return <OrganizationView id={id} />;
}
