"use client";

import { cn } from "@securefabric/ui/lib/utils";
import Image from "next/image";
import { CONNECTOR_LOGOS } from "@/lib/connector-catalog";

const NOT_ALPHANUMERIC = /[^A-Za-z0-9 ]/gu;

/** Two letters for a connector without a logo: "BD" for Black Duck SCA. */
function monogram(name: string): string {
	const words = name.replace(NOT_ALPHANUMERIC, " ").split(" ").filter(Boolean);
	const letters =
		words.length > 1 ? `${words[0]?.[0]}${words[1]?.[0]}` : name.slice(0, 2);
	return letters.toUpperCase();
}

/**
 * A connector's logo on a tile that reads in both themes: marks that are dark
 * on transparent ship a light twin (lib/connector-catalog.ts), and the tile
 * is white in light mode and a faint lift in dark mode, so coloured marks keep
 * their contrast. Without a logo, a monogram on the same tile.
 */
export function ConnectorLogo({
	id,
	name,
	size = 28,
	logo,
	className,
	muted = false,
}: {
	id: string;
	/** Used for the monogram when there's no logo. */
	name?: string;
	size?: number;
	logo?: string | null;
	className?: string;
	/** Greyscale, for connectors that aren't available yet. */
	muted?: boolean;
}) {
	const source = CONNECTOR_LOGOS[id] ?? (logo ? { light: logo } : undefined);
	const tile = cn(
		"border-border relative inline-flex shrink-0 items-center justify-center overflow-hidden border bg-white dark:bg-white/[0.06]",
		size >= 40 ? "rounded-lg" : "rounded-md",
		muted && "opacity-60 grayscale",
		className
	);
	if (!source) {
		return (
			<span
				aria-hidden="true"
				className={cn(tile, "text-muted-foreground bg-muted font-semibold")}
				style={{
					fontSize: Math.max(9, size * 0.34),
					height: size,
					width: size,
				}}
			>
				{monogram(name ?? id)}
			</span>
		);
	}
	const image = (src: string, extra?: string) => (
		<Image
			alt=""
			className={cn("size-full object-contain", extra)}
			height={size}
			src={src}
			unoptimized
			width={size}
		/>
	);
	return (
		<span
			aria-hidden="true"
			className={tile}
			style={{ height: size, padding: Math.round(size * 0.18), width: size }}
		>
			{source.dark ? (
				<>
					{image(source.light, "dark:hidden")}
					{image(source.dark, "hidden dark:block")}
				</>
			) : (
				image(source.light)
			)}
		</span>
	);
}
