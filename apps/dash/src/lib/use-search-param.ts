"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/**
 * One query-string parameter as state, limited to a known set of values.
 *
 * Tabs, categories and list filters live in the URL so the sidebar and the
 * ⌘K palette can link straight to them, a pasted link reopens the same view,
 * and Back undoes a click. Unknown values fall back to the default, and
 * setting the default removes the parameter so URLs stay short.
 */
export function useSearchParam<T extends string>(
	name: string,
	values: readonly T[],
	fallback: T
): [T, (value: T) => void] {
	const params = useSearchParams();
	const router = useRouter();
	const pathname = usePathname();
	const raw = params.get(name);
	const value = values.find((v) => v === raw) ?? fallback;

	const setValue = useCallback(
		(next: T) => {
			const updated = new URLSearchParams(params);
			if (next === fallback) {
				updated.delete(name);
			} else {
				updated.set(name, next);
			}
			const query = updated.toString();
			// replace, not push: a tab click isn't a page visit, and pushing
			// would make Back step through every tab before leaving.
			router.replace(query ? `${pathname}?${query}` : pathname, {
				scroll: false,
			});
		},
		[params, router, pathname, name, fallback]
	);

	return [value, setValue];
}
