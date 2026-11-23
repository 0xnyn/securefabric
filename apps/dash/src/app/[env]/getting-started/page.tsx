import { redirect } from "next/navigation";

/** Getting started became part of Keys; old links land there. */
export default async function Page({
	params,
}: {
	params: Promise<{ env: string }>;
}) {
	const { env } = await params;
	redirect(`/${env}/keys`);
}
