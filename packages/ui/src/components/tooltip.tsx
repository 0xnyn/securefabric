"use client";

import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip";
import type * as React from "react";

// ---------------------------------------------------------------------------
// Dialog

// ---------------------------------------------------------------------------
// Tooltip

export const TooltipProvider = TooltipPrimitive.Provider;

export function Tooltip({
	content,
	children,
}: {
	content: React.ReactNode;
	children: React.ReactElement;
}) {
	return (
		<TooltipPrimitive.Root>
			<TooltipPrimitive.Trigger render={children} />
			<TooltipPrimitive.Portal>
				<TooltipPrimitive.Positioner className="z-50" sideOffset={6}>
					<TooltipPrimitive.Popup className="border-border bg-popover shadow-float max-w-xs rounded-md border px-2 py-1 text-xs transition-opacity data-ending-style:opacity-0 data-starting-style:opacity-0">
						{content}
					</TooltipPrimitive.Popup>
				</TooltipPrimitive.Positioner>
			</TooltipPrimitive.Portal>
		</TooltipPrimitive.Root>
	);
}
