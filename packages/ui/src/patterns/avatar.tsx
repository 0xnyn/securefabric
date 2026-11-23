"use client";

import { color } from "@securefabric/tokens/tokens";
import BoringAvatar from "boring-avatars";
import { cn } from "../lib/utils";

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

const FIRST_LETTER_OR_DIGIT = /[\p{L}\p{N}]/u;

/** The first letter or digit of a name, upper-cased; "?" when there is none. */
function initial(name: string): string {
	const match = name.match(FIRST_LETTER_OR_DIGIT);
	return match ? match[0].toLocaleUpperCase() : "?";
}

function tileRadius(size: number): string {
	if (size >= 32) {
		return "rounded-lg";
	}
	return size >= 20 ? "rounded-md" : "rounded";
}

/**
 * An organization, account or other thing that isn't a person: its initial on
 * a plain rounded square. Generated art is for people only, so a customer
 * never reads as a teammate. Decorative: the name sits beside it.
 */
export function EntityAvatar({
	name,
	size = 32,
	className,
}: {
	name: string;
	size?: number;
	className?: string;
}) {
	return (
		<span
			aria-hidden="true"
			className={cn(
				"border-border bg-muted text-muted-foreground inline-flex shrink-0 items-center justify-center border leading-none font-medium select-none",
				tileRadius(size),
				className
			)}
			style={{
				fontSize: Math.max(9, Math.round(size * 0.45)),
				height: size,
				width: size,
			}}
		>
			{initial(name)}
		</span>
	);
}
