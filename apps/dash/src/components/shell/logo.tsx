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
