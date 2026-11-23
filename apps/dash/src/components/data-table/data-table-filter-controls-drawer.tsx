import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { FilterIcon } from "lucide-react";
import React from "react";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerClose,
	DrawerContent,
	DrawerDescription,
	DrawerFooter,
	DrawerHeader,
	DrawerTitle,
	DrawerTrigger,
} from "@/components/ui/drawer";
import { Kbd } from "@/components/ui/kbd";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { useHotKey } from "@/hooks/use-hot-key";
import { useMediaQuery } from "@/hooks/use-media-query";
import { DataTableFilterControls } from "./data-table-filter-controls";
import { TOOLTIP_DELAY } from "./ui-compat";

export function DataTableFilterControlsDrawer() {
	const triggerButtonRef = React.useRef<HTMLButtonElement>(null);
	const isMobile = useMediaQuery("(max-width: 640px)");

	useHotKey(
		() => {
			triggerButtonRef.current?.click();
		},
		"b",
		{ shift: true }
	); // securefabric: ⌘B is the app sidebar

	return (
		<Drawer>
			<TooltipProvider {...TOOLTIP_DELAY}>
				<Tooltip>
					<TooltipTrigger
						render={
							<DrawerTrigger
								render={
									<Button
										className="h-9 w-9"
										ref={isMobile ? triggerButtonRef : null}
										size="icon"
										variant="ghost"
									/>
								}
							/>
						}
					>
						<FilterIcon className="h-4 w-4" />
					</TooltipTrigger>
					<TooltipContent side="right">
						<p className="text-nowrap">
							Toggle controls with{" "}
							<Kbd className="text-muted-foreground group-hover:text-accent-foreground ml-1">
								<span className="mr-1">⌘⇧</span>
								<span>B</span>
							</Kbd>
						</p>
					</TooltipContent>
				</Tooltip>
			</TooltipProvider>
			<DrawerContent className="max-h-[calc(100dvh-4rem)]">
				<VisuallyHidden>
					<DrawerHeader>
						<DrawerTitle>Filters</DrawerTitle>
						<DrawerDescription>Adjust your table filters</DrawerDescription>
					</DrawerHeader>
				</VisuallyHidden>
				<div className="flex-1 overflow-y-auto px-4">
					<DataTableFilterControls />
				</div>
				<DrawerFooter>
					<DrawerClose render={<Button className="w-full" variant="outline" />}>
						Close
					</DrawerClose>
				</DrawerFooter>
			</DrawerContent>
		</Drawer>
	);
}
