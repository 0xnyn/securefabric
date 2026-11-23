"use client";

import { Switch as SwitchPrimitive } from "@base-ui/react/switch";

// ---------------------------------------------------------------------------
// Dialog

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
