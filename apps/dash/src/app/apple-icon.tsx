import { color } from "@securefabric/tokens/tokens";
import { ImageResponse } from "next/og";

const MARK_PATH =
	"M12 5.1L4 18.9H8.53L14.27 9.01ZM16.53 12.92H12L15.47 18.9H20Z";

export const size = { height: 180, width: 180 };
export const contentType = "image/png";

/** The home screen icon: the mark on the SecureFabric tile, square (iOS rounds the corners). */
export default function AppleIcon() {
	return new ImageResponse(
		<div
			style={{
				alignItems: "center",
				background: color.light.primary,
				display: "flex",
				height: "100%",
				justifyContent: "center",
				width: "100%",
			}}
		>
			{/* biome-ignore lint/a11y/noSvgWithoutTitle: drawn into a PNG */}
			<svg
				fill={color.light.primaryFg}
				fillOpacity={0.92}
				height={97}
				viewBox="4 4 16 16"
				width={88}
			>
				<path d={MARK_PATH} />
			</svg>
		</div>,
		size
	);
}
