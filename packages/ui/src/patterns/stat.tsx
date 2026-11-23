import type * as React from "react";
import { Card } from "../components/card";

export function Stat({
	label,
	value,
	hint,
}: {
	label: string;
	value: React.ReactNode;
	hint?: React.ReactNode;
}) {
	return (
		<Card className="grid gap-1 p-4">
			<span className="text-muted-foreground text-xs">{label}</span>
			<span className="text-2xl font-semibold tabular-nums">{value}</span>
			{hint ? (
				<span className="text-muted-foreground text-xs">{hint}</span>
			) : null}
		</Card>
	);
}
