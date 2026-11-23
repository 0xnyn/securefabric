"use client";

import { Button } from "@securefabric/ui/components/button";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import { useState } from "react";

/**
 * Keyset paging (API-02): a stack of cursors, so Back returns to exactly the
 * page you saw. `cursor` is what the current request sends.
 */
export function useCursorStack(): {
	cursor: string | undefined;
	page: number;
	next: (c: string | null | undefined) => void;
	prev: () => void;
	reset: () => void;
} {
	const [stack, setStack] = useState<string[]>([]);
	return {
		cursor: stack.at(-1),
		next: (c) => {
			if (c) {
				setStack((s) => [...s, c]);
			}
		},
		page: stack.length + 1,
		prev: () => setStack((s) => s.slice(0, -1)),
		reset: () => setStack([]),
	};
}

export function Pager({
	page,
	hasNext,
	onNext,
	onPrev,
	count,
}: {
	page: number;
	hasNext: boolean;
	onNext: () => void;
	onPrev: () => void;
	count?: number;
}) {
	return (
		<div className="text-muted-foreground flex items-center justify-between gap-2 py-3 text-sm">
			<span>
				Page {page}
				{count === undefined ? null : ` · ${count} shown`}
			</span>
			<div className="flex gap-1">
				<Button
					aria-label="Previous page"
					disabled={page <= 1}
					onClick={onPrev}
					size="sm"
					variant="outline"
				>
					<ChevronLeftIcon /> Previous
				</Button>
				<Button
					aria-label="Next page"
					disabled={!hasNext}
					onClick={onNext}
					size="sm"
					variant="outline"
				>
					Next <ChevronRightIcon />
				</Button>
			</div>
		</div>
	);
}
