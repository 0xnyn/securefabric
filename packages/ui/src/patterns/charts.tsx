"use client";

import { useId } from "react";
import {
	Area,
	AreaChart,
	Bar,
	BarChart,
	CartesianGrid,
	Cell,
	Pie,
	PieChart,
	Label as PieLabel,
	XAxis,
	YAxis,
} from "recharts";
import { compact, dateShort, num } from "../lib/format";
import { cn } from "../lib/utils";
import {
	type ChartConfig,
	ChartContainer,
	ChartLegend,
	ChartLegendContent,
	ChartTooltip,
	ChartTooltipContent,
} from "../primitives/chart";

/*
 * Charts on shadcn's ChartContainer (recharts underneath).
 *
 * Every colour is a CSS variable from the design tokens, set per series in a
 * ChartConfig, so light and dark come from the token files rather than from
 * here. The rules the marks follow (from the dataviz guidance): one y-axis,
 * a recessive dashed grid, 2px lines, 4px rounded data ends, a surface-
 * coloured gap between stacked segments, a legend whenever there are two or
 * more series, and a tooltip on hover. Status hues (warn for failures) only
 * ever mean status.
 */

/** A series: the key in each datum, its legend label, its colour. */
export interface Series {
	color: string;
	key: string;
	label: string;
}

const CHART_HEIGHT = 200;
const AXIS_TICK = { fontSize: 11 };
/** The 2px surface gap between stacked segments. */
const SEGMENT_GAP = { stroke: "var(--card)", strokeWidth: 2 };

function configOf(series: Series[]): ChartConfig {
	return Object.fromEntries(
		series.map((s) => [s.key, { color: s.color, label: s.label }])
	);
}

function Axes({ formatValue }: { formatValue: (n: number) => string }) {
	return (
		<>
			<CartesianGrid strokeDasharray="3 3" vertical={false} />
			<XAxis
				axisLine={false}
				dataKey="label"
				interval="preserveStartEnd"
				minTickGap={24}
				tick={AXIS_TICK}
				tickLine={false}
				tickMargin={8}
			/>
			<YAxis
				allowDecimals={false}
				axisLine={false}
				tick={AXIS_TICK}
				tickFormatter={formatValue}
				tickLine={false}
				tickMargin={4}
				width={40}
			/>
		</>
	);
}

/**
 * Change over time for a total that splits into parts: the parts stacked,
 * each with a soft gradient so the stack reads as one volume. The first
 * series sits on the baseline.
 */
export function StackedAreaChart({
	data,
	series,
	ariaLabel,
	height = CHART_HEIGHT,
	formatValue = compact,
}: {
	data: Record<string, number | string>[];
	series: Series[];
	ariaLabel: string;
	height?: number;
	formatValue?: (n: number) => string;
}) {
	const id = useId().replaceAll(":", "");
	return (
		<ChartContainer
			aria-label={ariaLabel}
			className="aspect-auto w-full"
			config={configOf(series)}
			role="img"
			style={{ height }}
		>
			<AreaChart data={data} margin={{ left: 0, right: 4, top: 4 }}>
				<defs>
					{series.map((s) => (
						<linearGradient
							id={`${id}-${s.key}`}
							key={s.key}
							x1="0"
							x2="0"
							y1="0"
							y2="1"
						>
							<stop
								offset="5%"
								stopColor={`var(--color-${s.key})`}
								stopOpacity={0.35}
							/>
							<stop
								offset="95%"
								stopColor={`var(--color-${s.key})`}
								stopOpacity={0.04}
							/>
						</linearGradient>
					))}
				</defs>
				<Axes formatValue={formatValue} />
				<ChartTooltip
					content={<ChartTooltipContent indicator="line" />}
					cursor={{ stroke: "var(--border)" }}
				/>
				{series.map((s) => (
					<Area
						dataKey={s.key}
						fill={`url(#${id}-${s.key})`}
						isAnimationActive={false}
						key={s.key}
						stackId="a"
						stroke={`var(--color-${s.key})`}
						strokeWidth={2}
						type="monotone"
					/>
				))}
				{series.length > 1 ? (
					<ChartLegend content={<ChartLegendContent />} />
				) : null}
			</AreaChart>
		</ChartContainer>
	);
}

/** Counts per bucket, split into parts. Only the top segment is rounded, so
 * the column keeps one silhouette. */
export function StackedBarChart({
	data,
	series,
	ariaLabel,
	height = CHART_HEIGHT,
	formatValue = compact,
}: {
	data: Record<string, number | string>[];
	series: Series[];
	ariaLabel: string;
	height?: number;
	formatValue?: (n: number) => string;
}) {
	return (
		<ChartContainer
			aria-label={ariaLabel}
			className="aspect-auto w-full"
			config={configOf(series)}
			role="img"
			style={{ height }}
		>
			<BarChart
				barCategoryGap="20%"
				data={data}
				margin={{ left: 0, right: 4, top: 4 }}
			>
				<Axes formatValue={formatValue} />
				<ChartTooltip
					content={<ChartTooltipContent />}
					cursor={{ fill: "var(--muted)", opacity: 0.6 }}
				/>
				{series.map((s, i) => (
					<Bar
						dataKey={s.key}
						fill={`var(--color-${s.key})`}
						isAnimationActive={false}
						key={s.key}
						radius={i === series.length - 1 ? [4, 4, 0, 0] : 0}
						stackId="a"
						{...SEGMENT_GAP}
					/>
				))}
				{series.length > 1 ? (
					<ChartLegend content={<ChartLegendContent />} />
				) : null}
			</BarChart>
		</ChartContainer>
	);
}

export interface DonutSlice {
	color: string;
	key: string;
	label: string;
	value: number;
}

/**
 * Parts of one small whole (connections by health). The total sits in the
 * hole and the legend beside it carries the labels and counts, so no slice
 * is identified by colour alone.
 */
export function DonutChart({
	slices,
	total,
	totalLabel,
	ariaLabel,
}: {
	slices: DonutSlice[];
	total: number;
	totalLabel: string;
	ariaLabel: string;
}) {
	const config: ChartConfig = Object.fromEntries(
		slices.map((s) => [s.key, { color: s.color, label: s.label }])
	);
	const data = slices.filter((s) => s.value > 0);
	return (
		<div className="flex items-center gap-6">
			<ChartContainer
				aria-label={ariaLabel}
				className="aspect-square h-36 shrink-0"
				config={config}
				role="img"
			>
				<PieChart>
					<ChartTooltip
						content={<ChartTooltipContent hideLabel nameKey="key" />}
					/>
					<Pie
						data={data}
						dataKey="value"
						innerRadius="68%"
						isAnimationActive={false}
						nameKey="key"
						outerRadius="100%"
						paddingAngle={data.length > 1 ? 2 : 0}
						strokeWidth={0}
					>
						{data.map((s) => (
							<Cell fill={`var(--color-${s.key})`} key={s.key} />
						))}
						<PieLabel
							content={({ viewBox }) => {
								if (!(viewBox && "cx" in viewBox)) {
									return null;
								}
								return (
									<text
										dominantBaseline="middle"
										textAnchor="middle"
										x={viewBox.cx}
										y={viewBox.cy}
									>
										<tspan
											className="fill-foreground text-xl font-semibold"
											x={viewBox.cx}
											y={(viewBox.cy ?? 0) - 6}
										>
											{num(total)}
										</tspan>
										<tspan
											className="fill-muted-foreground text-xs"
											x={viewBox.cx}
											y={(viewBox.cy ?? 0) + 14}
										>
											{totalLabel}
										</tspan>
									</text>
								);
							}}
						/>
					</Pie>
				</PieChart>
			</ChartContainer>
			<ul className="grid min-w-0 flex-1 gap-1.5 text-sm">
				{slices.map((s) => (
					<li className="flex items-center justify-between gap-3" key={s.key}>
						<span className="flex min-w-0 items-center gap-2">
							<span
								aria-hidden="true"
								className="size-2 shrink-0 rounded-sm"
								style={{ background: s.color }}
							/>
							<span className="truncate">{s.label}</span>
						</span>
						<span className="text-muted-foreground tabular-nums">
							{num(s.value)}
						</span>
					</li>
				))}
			</ul>
		</div>
	);
}

/** A thin single-series trend for stat tiles. Decorative: the number beside
 * it carries the value, so it has no axes and no tooltip. */
export function Sparkline({
	values,
	color = "var(--ds-accent)",
	className,
}: {
	values: number[];
	color?: string;
	className?: string;
}) {
	const id = useId().replaceAll(":", "");
	const data = values.map((value, i) => ({ i, value }));
	return (
		<div aria-hidden="true" className={cn("h-8 w-full", className)}>
			<ChartContainer
				className="aspect-auto size-full"
				config={{ value: { color, label: "Value" } }}
			>
				<AreaChart
					data={data}
					margin={{ bottom: 1, left: 0, right: 0, top: 2 }}
				>
					<defs>
						<linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
							<stop offset="0%" stopColor={color} stopOpacity={0.25} />
							<stop offset="100%" stopColor={color} stopOpacity={0} />
						</linearGradient>
					</defs>
					<Area
						dataKey="value"
						fill={`url(#${id})`}
						isAnimationActive={false}
						stroke={color}
						strokeWidth={2}
						type="monotone"
					/>
				</AreaChart>
			</ChartContainer>
		</div>
	);
}

/** A ranked list with proportional bars: the form for "share by entity",
 * where labels are long and the order matters more than the shape. */
export function BarList({
	items,
	formatValue = num,
}: {
	items: { key: string; label: React.ReactNode; value: number }[];
	formatValue?: (n: number) => string;
}) {
	const max = Math.max(1, ...items.map((i) => i.value));
	return (
		<ul className="grid gap-1.5">
			{items.map((item) => (
				<li
					className="relative flex h-8 items-center justify-between gap-3 px-2 text-sm"
					key={item.key}
				>
					<span
						aria-hidden="true"
						className="bg-ds-accent/10 absolute inset-y-0 left-0 rounded-sm"
						style={{ width: `${(item.value / max) * 100}%` }}
					/>
					<span className="relative flex min-w-0 items-center gap-2 truncate">
						{item.label}
					</span>
					<span className="text-muted-foreground relative tabular-nums">
						{formatValue(item.value)}
					</span>
				</li>
			))}
		</ul>
	);
}

/** A bucket's axis and tooltip label. Hourly buckets across several days
 * carry the day too: "11 PM" alone is ambiguous in a week of data. */
export function bucketLabel(
	start: number,
	bucketMs: number,
	multiDay = false
): string {
	if (bucketMs >= 86_400_000) {
		return dateShort(start);
	}
	const hour = new Date(start).toLocaleTimeString("en-US", { hour: "numeric" });
	return multiDay ? `${dateShort(start)}, ${hour}` : hour;
}
