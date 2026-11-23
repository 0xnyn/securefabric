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
	// No environment to land in (onboarding, an error, or an account with none):
	// `/dev` renders the shell, which explains each case. Without the empty
	// case this page would show the loading skeleton forever.
	const fallback =
		me.data?.needs_onboarding ||
		environments.isError ||
		me.isError ||
		environments.data?.length === 0;
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
