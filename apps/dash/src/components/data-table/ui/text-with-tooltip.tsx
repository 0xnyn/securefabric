import { cn } from "@securefabric/ui/lib/utils";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@securefabric/ui/primitives/tooltip";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import {
	TOOLTIP_DELAY,
	TOOLTIP_NOT_HOVERABLE,
} from "@/components/data-table/ui-compat";

interface TextWithTooltipProps {
	className?: string;
	style?: React.CSSProperties;
	text: string | number;
}

export function TextWithTooltip({
	text,
	className,
	style,
}: TextWithTooltipProps) {
	const [isTruncated, setIsTruncated] = useState<boolean>(false);
	const textRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const checkTruncation = () => {
			if (textRef.current) {
				const { scrollWidth, clientWidth } = textRef.current;
				setIsTruncated(scrollWidth > clientWidth);
			}
		};

		const resizeObserver = new ResizeObserver(() => {
			checkTruncation();
		});

		if (textRef.current) {
			resizeObserver.observe(textRef.current);
		}

		checkTruncation();

		return () => {
			resizeObserver.disconnect();
		};
	}, []);

	return (
		<TooltipProvider {...TOOLTIP_DELAY}>
			<Tooltip {...TOOLTIP_NOT_HOVERABLE}>
				<TooltipTrigger
					disabled={!isTruncated}
					render={
						<div
							className={cn(
								"truncate",
								!isTruncated && "pointer-events-none",
								className
							)}
							ref={textRef}
							style={style}
						/>
					}
				>
					{text}
				</TooltipTrigger>
				<TooltipContent>{text}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
}
