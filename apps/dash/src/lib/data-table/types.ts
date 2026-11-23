import { z } from "zod";

export const facetMetadataSchema = z.object({
	max: z.number().optional(),
	min: z.number().optional(),
	rows: z.array(z.object({ total: z.number(), value: z.any() })),
	total: z.number(),
});

export type FacetMetadataSchema = z.infer<typeof facetMetadataSchema>;

export type BaseChartSchema = { timestamp: number; [key: string]: number };
