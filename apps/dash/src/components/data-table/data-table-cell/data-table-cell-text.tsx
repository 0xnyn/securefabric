import { TextWithTooltip } from "@/components/custom/text-with-tooltip";

export function DataTableCellText({
	value,
	color,
}: {
	value: string | number;
	color?: string;
}) {
	return <TextWithTooltip style={color ? { color } : undefined} text={value} />;
}
