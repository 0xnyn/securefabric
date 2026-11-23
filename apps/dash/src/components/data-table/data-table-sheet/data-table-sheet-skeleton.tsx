import { cn } from "@securefabric/ui/lib/utils";
import { Skeleton } from "@securefabric/ui/primitives/skeleton";
import type { SheetField } from "../types";

interface SheetDetailsContentSkeletonProps<TData, TMeta> {
	fields: SheetField<TData, TMeta>[];
}

export function SheetDetailsContentSkeleton<TData, TMeta>({
	fields,
}: SheetDetailsContentSkeletonProps<TData, TMeta>) {
	return (
		<dl className="divide-y">
			{fields.map((field) => (
				<div
					className="flex items-center justify-between gap-4 py-2 text-sm"
					key={field.id.toString()}
				>
					<dt className="text-muted-foreground shrink-0">{field.label}</dt>
					<div>
						<Skeleton className={cn("h-5 w-52", field.skeletonClassName)} />
					</div>
				</div>
			))}
		</dl>
	);
}
