import type { Metadata } from "next";
import { StatusView } from "@/components/views/status";

export const metadata: Metadata = { title: "Status" };

export default function Page() {
	return <StatusView />;
}
