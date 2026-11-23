"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { Menu as MenuPrimitive } from "@base-ui/react/menu";
import { Select as SelectPrimitive } from "@base-ui/react/select";
import { Switch as SwitchPrimitive } from "@base-ui/react/switch";
import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip";
import { cn } from "@securefabric/ui/lib/utils";
import { CheckIcon, ChevronsUpDownIcon, XIcon } from "lucide-react";
import type * as React from "react";

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

// ---------------------------------------------------------------------------
// Select

export interface Option<T extends string = string> {
	description?: string;
	label: React.ReactNode;
	value: T;
}

export function Select<T extends string>({
	value,
	onChange,
	options,
	className,
	placeholder,
	ariaLabel,
	size = "md",
}: {
	value: T;
	onChange: (value: T) => void;
	options: Option<T>[];
	className?: string;
	placeholder?: string;
	ariaLabel?: string;
	size?: "sm" | "md";
}) {
	const items = options.map((o) => ({ label: o.label, value: o.value }));
	return (
		<SelectPrimitive.Root
			items={items}
			onValueChange={(v) => {
				if (v !== null) {
					onChange(v as T);
				}
			}}
			value={value}
		>
			<SelectPrimitive.Trigger
				aria-label={ariaLabel}
				className={cn(
					"border-input bg-background hover:bg-muted/60 focus-visible:ring-ring/20 inline-flex w-full min-w-0 items-center justify-between gap-2 rounded-md border px-3 text-left text-sm outline-none focus-visible:ring-2",
					size === "sm" ? "h-8" : "h-9",
					className
				)}
			>
				<span className="truncate">
					<SelectPrimitive.Value placeholder={placeholder} />
				</span>
				<SelectPrimitive.Icon className="text-muted-foreground">
					<ChevronsUpDownIcon className="size-3.5" />
				</SelectPrimitive.Icon>
			</SelectPrimitive.Trigger>
			<SelectPrimitive.Portal>
				<SelectPrimitive.Positioner
					alignItemWithTrigger={false}
					className="z-50 outline-none"
					sideOffset={4}
				>
					<SelectPrimitive.Popup className="border-border bg-popover shadow-float max-h-(--available-height) min-w-(--anchor-width) overflow-y-auto rounded-lg border p-1 transition-opacity duration-100 outline-none data-ending-style:opacity-0 data-starting-style:opacity-0">
						{options.map((o) => (
							<SelectPrimitive.Item
								className="data-highlighted:bg-muted relative flex cursor-default items-center gap-2 rounded-md py-1.5 pr-8 pl-2 text-sm outline-none select-none"
								key={o.value}
								value={o.value}
							>
								<div className="grid min-w-0">
									<SelectPrimitive.ItemText className="truncate">
										{o.label}
									</SelectPrimitive.ItemText>
									{o.description ? (
										<span className="text-muted-foreground truncate text-xs">
											{o.description}
										</span>
									) : null}
								</div>
								<SelectPrimitive.ItemIndicator className="absolute right-2">
									<CheckIcon className="size-3.5" />
								</SelectPrimitive.ItemIndicator>
							</SelectPrimitive.Item>
						))}
					</SelectPrimitive.Popup>
				</SelectPrimitive.Positioner>
			</SelectPrimitive.Portal>
		</SelectPrimitive.Root>
	);
}

// ---------------------------------------------------------------------------
// Switch

export function Switch({
	checked,
	onChange,
	ariaLabel,
	disabled,
	id,
}: {
	checked: boolean;
	onChange: (checked: boolean) => void;
	ariaLabel?: string;
	disabled?: boolean;
	id?: string;
}) {
	return (
		<SwitchPrimitive.Root
			aria-label={ariaLabel}
			checked={checked}
			className="bg-ds-line-accent focus-visible:ring-ring/40 data-checked:bg-primary relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border border-transparent transition-colors outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-50"
			disabled={disabled}
			id={id}
			onCheckedChange={onChange}
		>
			<SwitchPrimitive.Thumb className="bg-ds-bg block size-4 translate-x-0.5 rounded-full shadow-sm transition-transform data-checked:translate-x-4" />
		</SwitchPrimitive.Root>
	);
}

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
