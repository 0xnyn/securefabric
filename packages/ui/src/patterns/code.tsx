"use client";

import { useState } from "react";
import { cn } from "../lib/utils";
import { CopyButton } from "./copy";

// ---------------------------------------------------------------------------
// Copy

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
