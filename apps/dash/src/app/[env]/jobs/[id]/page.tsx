import type { Metadata } from "next";
import { JobView } from "@/components/views/connection";

export const metadata: Metadata = { title: "Job" };

export default async function Page({
	params,
}: {
	params: Promise<{ id: string }>;
}) {
	const { id } = await params;
	return <JobView id={id} />;
}
