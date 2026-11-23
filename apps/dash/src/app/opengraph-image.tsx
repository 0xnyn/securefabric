import { color } from "@securefabric/tokens/tokens";
import { ImageResponse } from "next/og";

const MARK_PATH =
	"M12 5.1L4 18.9H8.53L14.27 9.01ZM16.53 12.92H12L15.47 18.9H20Z";

export const alt = "SecureFabric: one API for every security tool";
export const size = { height: 630, width: 1200 };
export const contentType = "image/png";

/** The link preview when the dashboard URL is shared. */
export default function OpenGraphImage() {
	return new ImageResponse(
		<div
			style={{
				background: color.light.bg,
				color: color.light.fg,
				display: "flex",
				flexDirection: "column",
				height: "100%",
				justifyContent: "space-between",
				padding: 80,
				width: "100%",
			}}
		>
			<div style={{ alignItems: "center", display: "flex", gap: 20 }}>
				<div
					style={{
						alignItems: "center",
						background: color.light.primary,
						borderRadius: 16,
						display: "flex",
						height: 72,
						justifyContent: "center",
						width: 72,
					}}
				>
					{/* biome-ignore lint/a11y/noSvgWithoutTitle: drawn into a PNG */}
					<svg
						fill={color.light.primaryFg}
						height={40}
						viewBox="4 4 16 16"
						width={40}
					>
						<path d={MARK_PATH} />
					</svg>
				</div>
				<span style={{ fontSize: 40, fontWeight: 600 }}>SecureFabric</span>
			</div>
			<div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
				<span
					style={{
						fontSize: 72,
						fontWeight: 600,
						letterSpacing: -2,
						lineHeight: 1.05,
					}}
				>
					One API for every security tool
				</span>
				<span style={{ color: color.light.muted, fontSize: 32 }}>
					Vulnerabilities, devices, alerts and identities from 90+ vendors,
					normalized into one schema.
				</span>
			</div>
		</div>,
		size
	);
}
