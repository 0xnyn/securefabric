"use client";

import * as SheetPrimitive from "@radix-ui/react-dialog";
import { cn } from "@securefabric/ui/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "lucide-react";
import * as React from "react";
import { boxRadiusClassName } from "@/lib/style";

const Sheet = SheetPrimitive.Root;

const SheetTrigger = SheetPrimitive.Trigger;

/**
 * Radix's close, plus Base UI's `render`.
 *
 * The shadcn CLI rewrites `asChild` into `render={<child />}` when it installs
 * into a Base UI project. This sheet is built on Radix in both cases — it
 * ships with the block rather than resolving from the project's library — so
 * it has to accept the prop the CLI writes.
 */
function SheetClose({
	render,
	children,
	...props
}: React.ComponentProps<typeof SheetPrimitive.Close> & {
	render?: React.ReactElement;
}) {
	if (!render) {
		return <SheetPrimitive.Close {...props}>{children}</SheetPrimitive.Close>;
	}

	// `asChild` is spread rather than written as an attribute so the same CLI
	// codemod doesn't rewrite it here, inside the component implementing it.
	return (
		<SheetPrimitive.Close {...{ asChild: true }} {...props}>
			{children === undefined
				? render
				: React.cloneElement(render, undefined, children)}
		</SheetPrimitive.Close>
	);
}

const SheetPortal = SheetPrimitive.Portal;

function SheetOverlay({
	className,
	...props
}: React.ComponentProps<typeof SheetPrimitive.Overlay>) {
	return (
		<SheetPrimitive.Overlay
			className={cn(
				"bg-background/40 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50",
				className
			)}
			data-slot="sheet-overlay"
			{...props}
		/>
	);
}

const sheetVariants = cva(
	"bg-background border-border shadow-float data-[state=open]:animate-in data-[state=closed]:animate-out ease-out-quint fixed z-50 gap-4 rounded-xl border p-6 transition data-[state=closed]:duration-200 data-[state=open]:duration-300",
	{
		defaultVariants: {
			side: "right",
		},
		variants: {
			side: {
				bottom:
					"data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom inset-x-2 bottom-2",
				left: "data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left inset-y-2 left-2 w-3/4 sm:max-w-sm",
				right:
					"data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right inset-y-2 right-2 w-[calc(100%-1rem)] sm:max-w-sm",
				top: "data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top inset-x-2 top-2",
			},
		},
	}
);

interface SheetContentProps
	extends React.ComponentProps<typeof SheetPrimitive.Content>,
		VariantProps<typeof sheetVariants> {
	hideClose?: boolean;
}

function SheetContent({
	side = "right",
	className,
	children,
	hideClose,
	...props
}: SheetContentProps) {
	return (
		<SheetPortal>
			<SheetOverlay />
			<SheetPrimitive.Content
				className={cn(sheetVariants({ side }), className)}
				data-slot="sheet-content"
				{...props}
			>
				{children}
				{hideClose ? null : (
					<SheetPrimitive.Close
						autoFocus={true}
						className={cn(
							"data-[state=open]:bg-secondary focus-visible:border-ring focus-visible:ring-ring/50 absolute top-4 right-4 opacity-70 transition-all outline-none hover:opacity-100 focus-visible:ring-[3px] disabled:pointer-events-none",
							boxRadiusClassName
						)}
					>
						<X className="h-4 w-4" />
						<span className="sr-only">Close</span>
					</SheetPrimitive.Close>
				)}
			</SheetPrimitive.Content>
		</SheetPortal>
	);
}

function SheetHeader({
	className,
	...props
}: React.HTMLAttributes<HTMLDivElement>) {
	return (
		<div
			className={cn(
				"flex flex-col space-y-2 text-center sm:text-left",
				className
			)}
			{...props}
		/>
	);
}

function SheetFooter({
	className,
	...props
}: React.HTMLAttributes<HTMLDivElement>) {
	return (
		<div
			className={cn(
				"flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
				className
			)}
			{...props}
		/>
	);
}

function SheetTitle({
	className,
	...props
}: React.ComponentProps<typeof SheetPrimitive.Title>) {
	return (
		<SheetPrimitive.Title
			className={cn("text-foreground text-lg font-semibold", className)}
			data-slot="sheet-title"
			{...props}
		/>
	);
}

function SheetDescription({
	className,
	...props
}: React.ComponentProps<typeof SheetPrimitive.Description>) {
	return (
		<SheetPrimitive.Description
			className={cn("text-muted-foreground text-sm", className)}
			data-slot="sheet-description"
			{...props}
		/>
	);
}

export {
	Sheet,
	SheetClose,
	SheetContent,
	SheetDescription,
	SheetFooter,
	SheetHeader,
	SheetOverlay,
	SheetPortal,
	SheetTitle,
	SheetTrigger,
};
