import { TextWithTooltip } from "@/components/data-table/ui/text-with-tooltip";

export function DataTableCellText({
	value,
	color,
}: {
	value: string | number;
	color?: string;
}) {
	return <TextWithTooltip style={color ? { color } : undefined} text={value} />;
}
