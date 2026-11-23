"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { XIcon } from "lucide-react";
import type * as React from "react";
import { cn } from "../lib/utils";

// ---------------------------------------------------------------------------
// Dialog

export function Dialog({
	open,
	onOpenChange,
	children,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	children: React.ReactNode;
}) {
	return (
		<DialogPrimitive.Root onOpenChange={onOpenChange} open={open}>
			{children}
		</DialogPrimitive.Root>
	);
}

const BACKDROP =
	"fixed inset-0 z-50 bg-ds-bg/70 backdrop-blur-[2px] transition-opacity duration-150 data-ending-style:opacity-0 data-starting-style:opacity-0";

export function DialogContent({
	title,
	description,
	children,
	footer,
	className,
}: {
	title: React.ReactNode;
	description?: React.ReactNode;
	children?: React.ReactNode;
	footer?: React.ReactNode;
	className?: string;
}) {
	return (
		<DialogPrimitive.Portal>
			<DialogPrimitive.Backdrop className={BACKDROP} />
			<DialogPrimitive.Popup
				className={cn(
					"border-border bg-card shadow-float fixed top-1/2 left-1/2 z-50 flex max-h-[calc(100svh-2rem)] w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border transition-all duration-150 outline-none data-ending-style:scale-95 data-ending-style:opacity-0 data-starting-style:scale-95 data-starting-style:opacity-0",
					className
				)}
			>
				<div className="flex items-start justify-between gap-4 px-6 pt-6 pb-4">
					<div className="grid gap-1">
						<DialogPrimitive.Title className="tracking-heading text-lg font-semibold">
							{title}
						</DialogPrimitive.Title>
						{description ? (
							<DialogPrimitive.Description className="text-muted-foreground text-sm">
								{description}
							</DialogPrimitive.Description>
						) : null}
					</div>
					<DialogPrimitive.Close
						aria-label="Close"
						className="text-muted-foreground hover:bg-muted hover:text-foreground -mt-1 -mr-2 rounded-md p-1.5"
					>
						<XIcon className="size-4" />
					</DialogPrimitive.Close>
				</div>
				<div className="min-h-0 flex-1 overflow-y-auto px-6 pb-6">
					{children}
				</div>
				{footer ? (
					<div className="border-border bg-ds-shell flex items-center justify-end gap-2 border-t px-6 py-3">
						{footer}
					</div>
				) : null}
			</DialogPrimitive.Popup>
		</DialogPrimitive.Portal>
	);
}

/** A panel that slides in from the right, for details beside a list. */
export function SheetContent({
	title,
	description,
	children,
	className,
	actions,
}: {
	title: React.ReactNode;
	description?: React.ReactNode;
	children: React.ReactNode;
	className?: string;
	actions?: React.ReactNode;
}) {
	return (
		<DialogPrimitive.Portal>
			<DialogPrimitive.Backdrop className={BACKDROP} />
			<DialogPrimitive.Popup
				className={cn(
					"border-border bg-card shadow-float ease-out-quint fixed inset-y-2 right-2 z-50 flex w-[calc(100%-1rem)] max-w-2xl flex-col overflow-hidden rounded-xl border transition-transform duration-200 outline-none data-ending-style:translate-x-[calc(100%+1rem)] data-starting-style:translate-x-[calc(100%+1rem)]",
					className
				)}
			>
				<div className="border-border flex items-start justify-between gap-4 border-b px-6 py-4">
					<div className="grid min-w-0 gap-1">
						<DialogPrimitive.Title className="truncate text-base font-semibold">
							{title}
						</DialogPrimitive.Title>
						{description ? (
							<DialogPrimitive.Description className="text-muted-foreground text-sm">
								{description}
							</DialogPrimitive.Description>
						) : null}
					</div>
					<div className="flex items-center gap-2">
						{actions}
						<DialogPrimitive.Close
							aria-label="Close"
							className="text-muted-foreground hover:bg-muted hover:text-foreground rounded-md p-1.5"
						>
							<XIcon className="size-4" />
						</DialogPrimitive.Close>
					</div>
				</div>
				<div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
			</DialogPrimitive.Popup>
		</DialogPrimitive.Portal>
	);
}
