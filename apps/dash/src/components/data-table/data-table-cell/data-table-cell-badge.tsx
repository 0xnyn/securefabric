import { cn } from "@securefabric/ui/lib/utils";
import { boxRadiusClassName } from "@/lib/style";

export function DataTableCellBadge({
	value,
	color,
}: {
	value: string | number;
	color?: string;
}) {
	return (
		<span
			className={cn(
				"border px-1.5 py-0.5 font-mono text-xs",
				boxRadiusClassName
			)}
			style={
				color
					? {
							backgroundColor: `${color}1a`,
							borderColor: `${color}33`,
							color,
						}
					: undefined
			}
		>
			{value}
		</span>
	);
}
