import type * as React from "react";
import { cn } from "../lib/utils";

export function Table({ className, ...props }: React.ComponentProps<"table">) {
	return (
		<div className="w-full overflow-x-auto">
			<table className={cn("w-full text-sm", className)} {...props} />
		</div>
	);
}

export function Th({ className, ...props }: React.ComponentProps<"th">) {
	return (
		<th
			className={cn(
				"border-border text-muted-foreground h-10 border-b px-4 text-left text-xs font-medium whitespace-nowrap first:pl-5 last:pr-5",
				className
			)}
			{...props}
		/>
	);
}

export function Td({ className, ...props }: React.ComponentProps<"td">) {
	return (
		<td
			className={cn(
				"border-border h-12 border-b px-4 align-middle group-last/row:border-b-0 first:pl-5 last:pr-5",
				className
			)}
			{...props}
		/>
	);
}

export function Tr({ className, ...props }: React.ComponentProps<"tr">) {
	return (
		<tr
			className={cn("group/row hover:bg-ds-shell transition-colors", className)}
			{...props}
		/>
	);
}
