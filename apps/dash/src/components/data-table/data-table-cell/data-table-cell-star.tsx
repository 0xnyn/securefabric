import { Star } from "lucide-react";

export function DataTableCellStar({ value }: { value: boolean }) {
	if (value) {
		return (
			<span className="ml-auto inline-flex items-center">
				<Star
					aria-hidden="true"
					className="h-4 w-4 fill-yellow-400 text-yellow-400"
				/>
				<span className="sr-only">Favorited</span>
			</span>
		);
	}
	return (
		<span className="ml-auto inline-flex items-center">
			<Star aria-hidden="true" className="text-muted-foreground/40 h-4 w-4" />
			<span className="sr-only">Not favorited</span>
		</span>
	);
}
