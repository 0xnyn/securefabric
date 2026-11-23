"use client";

import { createContext, useContext, useMemo } from "react";
import { type Access, accessFor } from "@/lib/access";
import type { ApiClient } from "@/lib/api";
import type { Environment, Me } from "@/lib/types";

interface EnvContextValue {
	/** A client that sends `X-Environment-Id` for this environment. */
	client: ApiClient;
	/** The dashboard is using a development API key instead of a session. */
	devMode: boolean;
	/** The environment in the URL. */
	env: Environment;
	/** Every environment of the account (an API key sees only its own). */
	environments: Environment[];
	me: Me;
}

export const EnvContext = createContext<EnvContextValue | null>(null);

/** The current environment, account and API client. Only valid under the
 * env layout, which renders its children once they have loaded. */
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

/** What the signed-in person (or the dev API key) may see and do. */
export function useAccess(): Access {
	const { me } = useEnv();
	return useMemo(() => accessFor(me), [me]);
}
