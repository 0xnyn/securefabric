import { addDays, addHours, endOfDay, startOfDay } from "date-fns";
import type { DatePreset } from "@/components/data-table/types";

export const presets = [
	{
		from: startOfDay(new Date()),
		label: "Today",
		shortcut: "d", // day
		to: endOfDay(new Date()),
	},
	{
		from: startOfDay(addDays(new Date(), -1)),
		label: "Yesterday",
		shortcut: "y",
		to: endOfDay(addDays(new Date(), -1)),
	},
	{
		from: addHours(new Date(), -1),
		label: "Last hour",
		shortcut: "h",
		to: new Date(),
	},
	{
		from: startOfDay(addDays(new Date(), -7)),
		label: "Last 7 days",
		shortcut: "w",
		to: endOfDay(new Date()),
	},
	{
		from: startOfDay(addDays(new Date(), -14)),
		label: "Last 14 days",
		shortcut: "b", // bi-weekly
		to: endOfDay(new Date()),
	},
	{
		from: startOfDay(addDays(new Date(), -30)),
		label: "Last 30 days",
		shortcut: "m",
		to: endOfDay(new Date()),
	},
] satisfies DatePreset[];
