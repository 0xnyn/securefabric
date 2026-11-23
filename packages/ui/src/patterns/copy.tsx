"use client";
import { CheckIcon, CopyIcon, EyeIcon, EyeOffIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { mask } from "../lib/format";
import { cn } from "../lib/utils";

// ---------------------------------------------------------------------------
// Copy

export function useCopy(): [boolean, (text: string, label?: string) => void] {
	const [copied, setCopied] = useState(false);
	const copy = (text: string, label?: string): void => {
		navigator.clipboard
			.writeText(text)
			.then(() => {
				setCopied(true);
				if (label) {
					toast.success(`${label} copied`);
				}
				setTimeout(() => setCopied(false), 1400);
			})
			.catch(() =>
				toast.error("Couldn't copy to the clipboard", {
					description: "Select the text and copy it yourself.",
				})
			);
	};
	return [copied, copy];
}

export function CopyButton({
	value,
	label,
	className,
	variant = "ghost",
}: {
	value: string;
	label?: string;
	className?: string;
	variant?: "ghost" | "code";
}) {
	const [copied, copy] = useCopy();
	return (
		<button
			aria-label={label ? `Copy ${label}` : "Copy"}
			className={cn(
				"inline-flex size-7 shrink-0 items-center justify-center rounded-md transition-colors",
				variant === "code"
					? "text-ds-code-muted hover:bg-ds-code-fg/10 hover:text-ds-code-fg"
					: "text-muted-foreground hover:bg-muted hover:text-foreground",
				className
			)}
			onClick={() => copy(value, label)}
			type="button"
		>
			{copied ? (
				<CheckIcon className="size-3.5" />
			) : (
				<CopyIcon className="size-3.5" />
			)}
		</button>
	);
}

/** A value in a mono field with a copy button, for keys and IDs. */
export function CopyField({
	value,
	display,
	label,
	className,
}: {
	value: string;
	display?: string;
	label?: string;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"border-border bg-ds-shell flex h-9 min-w-0 items-center gap-2 rounded-md border pr-1 pl-3",
				className
			)}
		>
			<span className="text-code min-w-0 flex-1 truncate font-mono">
				{display ?? value}
			</span>
			<CopyButton label={label} value={value} />
		</div>
	);
}

/** A secret in a mono field: masked until revealed, with a copy button. */
export function SecretRow({
	label,
	value,
	help,
}: {
	label: string;
	value: string;
	help: string;
}) {
	const [shown, setShown] = useState(false);
	return (
		<div className="grid gap-1.5">
			<span className="text-sm font-medium">{label}</span>
			<div className="border-border bg-ds-shell flex h-9 items-center gap-1 rounded-md border pr-1 pl-3">
				<span className="text-code min-w-0 flex-1 truncate font-mono">
					{shown ? value : mask(value)}
				</span>
				<button
					aria-label={shown ? `Hide ${label}` : `Reveal ${label}`}
					className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-7 items-center justify-center rounded-md"
					onClick={() => setShown(!shown)}
					type="button"
				>
					{shown ? (
						<EyeOffIcon className="size-3.5" />
					) : (
						<EyeIcon className="size-3.5" />
					)}
				</button>
				<CopyButton label={label} value={value} />
			</div>
			<p className="text-muted-foreground text-xs">{help}</p>
		</div>
	);
}
