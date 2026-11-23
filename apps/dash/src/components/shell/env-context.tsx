"use client";

import { createContext, useContext } from "react";
import type { Environment, Workspace } from "@/lib/types";

interface EnvContextValue {
	env: Environment;
	workspace: Workspace;
}

export const EnvContext = createContext<EnvContextValue | null>(null);

/** The current environment and workspace. Only valid under the env layout,
 * which renders its children once the workspace has loaded. */
export function useEnv(): EnvContextValue {
	const value = useContext(EnvContext);
	if (!value) {
		throw new Error("useEnv must be used under the environment layout");
	}
	return value;
}

/** Builds an href inside the current environment. */
export function useHref(): (path?: string) => string {
	const { env } = useEnv();
	return (path = "") => `/${env.slug}${path}`;
}
