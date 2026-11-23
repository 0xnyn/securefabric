"use client";

import { color } from "@securefabric/tokens/tokens";
import { cn } from "@securefabric/ui/lib/utils";
import BoringAvatar from "boring-avatars";
import { CheckIcon, CopyIcon, EyeIcon, EyeOffIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { mask } from "@/lib/format";

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
			.catch(() => toast.error("Couldn't copy to the clipboard"));
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

// ---------------------------------------------------------------------------
// Code

const JSON_LINE =
	/^(?<indent>\s*)(?<key>"[^"]+":\s?)?(?<value>.*?)(?<comma>,?)$/u;
const COMMENT_LINE = /^\s*(?:\/\/|#)/u;

function CodeLine({ line, json }: { line: string; json: boolean }) {
	if (COMMENT_LINE.test(line)) {
		return <span className="text-ds-code-muted">{line}</span>;
	}
	if (!json) {
		return <span>{line}</span>;
	}
	const m = JSON_LINE.exec(line);
	if (!m?.groups) {
		return <span>{line}</span>;
	}
	const { indent, key, value, comma } = m.groups;
	const isString = value?.startsWith('"');
	return (
		<span>
			{indent}
			{key ? <span className="text-ds-code-muted">{key}</span> : null}
			<span className={isString ? "text-ds-code-fg" : "text-ds-code-fg/80"}>
				{value}
			</span>
			{comma}
		</span>
	);
}

export function CodeBlock({
	code,
	json = false,
	className,
	title,
	actions,
	maxHeight,
}: {
	code: string;
	json?: boolean;
	className?: string;
	title?: React.ReactNode;
	actions?: React.ReactNode;
	maxHeight?: string;
}) {
	const lines = code.split("\n");
	return (
		<div
			className={cn(
				"border-border bg-ds-code text-ds-code-fg overflow-hidden rounded-lg border",
				className
			)}
		>
			<div className="border-ds-code-fg/10 flex h-10 items-center justify-between gap-2 border-b pr-1.5 pl-4">
				<div className="text-2xs text-ds-code-muted flex min-w-0 items-center gap-3">
					{title}
				</div>
				<div className="flex items-center gap-1">
					{actions}
					<CopyButton label="Code" value={code} variant="code" />
				</div>
			</div>
			<pre
				className="text-code overflow-auto p-4 font-mono leading-relaxed"
				style={maxHeight ? { maxHeight } : undefined}
			>
				<code>
					{lines.map((line, i) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: lines are static text with no identity.
						<div key={i}>
							<CodeLine json={json} line={line} />
						</div>
					))}
				</code>
			</pre>
		</div>
	);
}

/** Tabs across the top of a code block: curl, TypeScript, Python. */
export function CodeTabs({
	samples,
	className,
	maxHeight,
}: {
	samples: { label: string; code: string; json?: boolean }[];
	className?: string;
	maxHeight?: string;
}) {
	const [active, setActive] = useState(0);
	const sample = samples[active] ?? samples[0];
	if (!sample) {
		return null;
	}
	return (
		<CodeBlock
			className={className}
			code={sample.code}
			json={sample.json}
			maxHeight={maxHeight}
			title={
				<div className="-ml-1 flex items-center gap-1" role="tablist">
					{samples.map((s, i) => (
						<button
							aria-selected={i === active}
							className={cn(
								"rounded px-2 py-1 font-sans text-xs transition-colors",
								i === active
									? "bg-ds-code-fg/10 text-ds-code-fg"
									: "text-ds-code-muted hover:text-ds-code-fg"
							)}
							key={s.label}
							onClick={() => setActive(i)}
							role="tab"
							type="button"
						>
							{s.label}
						</button>
					))}
				</div>
			}
		/>
	);
}

// ---------------------------------------------------------------------------
// Layout

export function PageHeader({
	title,
	description,
	actions,
	children,
}: {
	title: React.ReactNode;
	description?: React.ReactNode;
	actions?: React.ReactNode;
	children?: React.ReactNode;
}) {
	return (
		<div className="border-border bg-background border-b">
			<div className="flex flex-col gap-4 px-4 py-7 sm:flex-row sm:items-end sm:justify-between sm:px-8">
				<div className="grid min-w-0 gap-1.5">
					<h1 className="tracking-heading text-2xl font-semibold">{title}</h1>
					{description ? (
						<p className="text-muted-foreground max-w-2xl text-sm">
							{description}
						</p>
					) : null}
				</div>
				{actions ? (
					<div className="flex shrink-0 flex-wrap items-center gap-2">
						{actions}
					</div>
				) : null}
			</div>
			{children}
		</div>
	);
}

export function PageBody({
	className,
	children,
}: {
	className?: string;
	children: React.ReactNode;
}) {
	return (
		<div className={cn("w-full px-4 py-7 sm:px-8", className)}>{children}</div>
	);
}

/** Underlined tabs, Vercel style, for sections inside a page. */
export function Tabs<T extends string>({
	tabs,
	value,
	onChange,
	className,
}: {
	tabs: { value: T; label: React.ReactNode; count?: number }[];
	value: T;
	onChange: (value: T) => void;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"border-border -mb-px flex gap-1 overflow-x-auto border-b",
				className
			)}
			role="tablist"
		>
			{tabs.map((t) => {
				const active = t.value === value;
				return (
					<button
						aria-selected={active}
						className={cn(
							"relative flex h-10 shrink-0 items-center gap-1.5 px-3 text-sm transition-colors",
							active
								? "text-foreground after:bg-foreground after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full"
								: "text-muted-foreground hover:text-foreground"
						)}
						key={t.value}
						onClick={() => onChange(t.value)}
						role="tab"
						type="button"
					>
						{t.label}
						{t.count === undefined ? null : (
							<span className="bg-muted text-2xs text-muted-foreground rounded-full px-1.5">
								{t.count}
							</span>
						)}
					</button>
				);
			})}
		</div>
	);
}

export function KeyValue({
	items,
	className,
}: {
	items: { label: string; value: React.ReactNode }[];
	className?: string;
}) {
	return (
		<dl className={cn("grid gap-x-6 gap-y-4 sm:grid-cols-2", className)}>
			{items.map((item) => (
				<div className="grid min-w-0 gap-1" key={item.label}>
					<dt className="text-muted-foreground text-xs">{item.label}</dt>
					<dd className="min-w-0 truncate text-sm">{item.value}</dd>
				</div>
			))}
		</dl>
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

/** Brand indigos plus the navy ground, so every avatar reads as SecureFabric. */
const AVATAR_COLORS = [
	color.light.primary,
	color.light.primaryMid,
	color.dark.accent,
	color.light.primaryLight,
	color.light.fg,
];

/**
 * A person's avatar, generated from a stable seed (their email) so the same
 * person always gets the same face. Decorative: the name sits beside it.
 */
export function PersonAvatar({
	seed,
	size = 32,
	className,
}: {
	seed: string;
	size?: number;
	className?: string;
}) {
	return (
		<span
			aria-hidden="true"
			className={cn("inline-flex shrink-0 rounded-full", className)}
		>
			<BoringAvatar
				colors={AVATAR_COLORS}
				name={seed}
				size={size}
				variant="beam"
			/>
		</span>
	);
}
