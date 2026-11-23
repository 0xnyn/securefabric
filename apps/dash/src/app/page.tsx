"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { LoadingShell, useAccount } from "@/components/shell/shell";

/**
 * Land in the first environment of the account (usually `dev`). A first
 * sign-in has no account yet: the environment shell shows onboarding, so
 * that case (and an error listing environments) goes to `/dev` too.
 */
export default function Home() {
	const router = useRouter();
	const { environments, me } = useAccount();
	const first =
		environments.data?.find((e) => e.slug === "dev") ?? environments.data?.[0];
	const fallback =
		me.data?.needs_onboarding || environments.isError || me.isError;
	let target: string | null = null;
	if (first) {
		target = `/${first.slug}`;
	} else if (fallback) {
		target = "/dev";
	}
	useEffect(() => {
		if (target) {
			router.replace(target);
		}
	}, [target, router]);
	return <LoadingShell />;
}
