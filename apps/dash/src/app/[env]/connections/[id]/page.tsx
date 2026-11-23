import type { Metadata } from "next";
import { ConnectionView } from "@/components/views/connection";

export const metadata: Metadata = { title: "Connection" };

export default async function Page({
	params,
}: {
	params: Promise<{ id: string }>;
}) {
	const { id } = await params;
	return <ConnectionView id={id} />;
}
