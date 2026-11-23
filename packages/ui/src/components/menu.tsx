"use client";

import { Menu as MenuPrimitive } from "@base-ui/react/menu";
import type * as React from "react";
import { cn } from "../lib/utils";

// ---------------------------------------------------------------------------
// Dialog

// ---------------------------------------------------------------------------
// Menu

export const Menu = MenuPrimitive.Root;

export const MenuTrigger = MenuPrimitive.Trigger;

export function MenuContent({
	children,
	align = "start",
	className,
	sideOffset = 6,
}: {
	children: React.ReactNode;
	align?: "start" | "center" | "end";
	className?: string;
	sideOffset?: number;
}) {
	return (
		<MenuPrimitive.Portal>
			<MenuPrimitive.Positioner
				align={align}
				className="z-50 outline-none"
				sideOffset={sideOffset}
			>
				<MenuPrimitive.Popup
					className={cn(
						"border-border bg-popover shadow-float min-w-48 origin-(--transform-origin) rounded-lg border p-1 transition-[opacity,scale] duration-100 outline-none data-ending-style:scale-95 data-ending-style:opacity-0 data-starting-style:scale-95 data-starting-style:opacity-0",
						className
					)}
				>
					{children}
				</MenuPrimitive.Popup>
			</MenuPrimitive.Positioner>
		</MenuPrimitive.Portal>
	);
}

export function MenuItem({
	className,
	...props
}: React.ComponentProps<typeof MenuPrimitive.Item>) {
	return (
		<MenuPrimitive.Item
			className={cn(
				"data-highlighted:bg-muted [&_svg]:text-muted-foreground flex cursor-default items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none select-none [&_svg]:size-4",
				className
			)}
			{...props}
		/>
	);
}

export function MenuLabel({ children }: { children: React.ReactNode }) {
	return (
		<div className="text-muted-foreground px-2 pt-1.5 pb-1 text-xs">
			{children}
		</div>
	);
}

export function MenuSeparator() {
	return <MenuPrimitive.Separator className="bg-border -mx-1 my-1 h-px" />;
}
