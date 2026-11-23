const LOGO_PATH =
	"M12 5.1L4 18.9H8.53L14.27 9.01ZM16.53 12.92H12L15.47 18.9H20Z";

export function Logo({ className }: { className?: string }) {
	return (
		<svg
			aria-hidden="true"
			className={className}
			fill="currentColor"
			viewBox="4 4 16 16"
		>
			<path d={LOGO_PATH} />
		</svg>
	);
}

/** The brand colour, also the connect page's default accent. */
export const BRAND_ACCENT = "#533AFD";

/** The full-colour mark (app/icon.svg): the glyph on an indigo tile. Reads
 * the same in both themes, so it's the default logo wherever a customer
 * hasn't set their own. */
export function BrandMark({
	size = 24,
	className,
}: {
	size?: number;
	className?: string;
}) {
	return (
		<svg
			aria-hidden="true"
			className={className}
			height={size}
			viewBox="0 0 24 24"
			width={size}
		>
			<rect fill={BRAND_ACCENT} height="24" rx="5.28" width="24" />
			<path
				d={LOGO_PATH}
				fill="#ffffff"
				fillOpacity="0.92"
				transform="translate(0.84 0.84) scale(0.93)"
			/>
		</svg>
	);
}
