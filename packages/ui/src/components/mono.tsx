import type * as React from "react";
import { cn } from "../lib/utils";

export function Mono({ className, ...props }: React.ComponentProps<"span">) {
	return <span className={cn("text-code font-mono", className)} {...props} />;
}
