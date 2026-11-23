"use client";

import * as React from "react";
import { DataTableFilterCommand } from "@/components/data-table/data-table-filter-command";
import { DataTableInfinite } from "@/components/data-table/data-table-infinite";
import { useDataTable } from "@/components/data-table/data-table-provider";
import { MemoizedDataTableSheetContent } from "@/components/data-table/data-table-sheet/data-table-sheet-content";
import { DataTableSheetDetails } from "@/components/data-table/data-table-sheet/data-table-sheet-details";
import type { SheetField } from "@/components/data-table/types";
import { useMemoryAdapter } from "@/lib/store/adapters/memory";
import { DataTableStoreProvider } from "@/lib/store/provider/DataTableStoreProvider";
import { field } from "@/lib/store/schema";
import type { SchemaDefinition } from "@/lib/store/schema/types";
import {
	createTableSchema,
	generateColumns,
	generateFilterFields,
	generateFilterSchema,
	generateSheetFields,
	getDefaultColumnVisibility,
} from "@/lib/table-schema";
import { inferSchemaFromJSON } from "@/lib/table-schema/infer";

type AutoRow = Record<string, unknown>;

export interface DataTableAutoProps {
	data: AutoRow[];
}

export function DataTableAuto({ data }: DataTableAutoProps) {
	const schemaJson = React.useMemo(() => inferSchemaFromJSON(data), [data]);

	const { definition } = React.useMemo(
		() => createTableSchema.fromJSON(schemaJson),
		[schemaJson]
	);

	const columns = React.useMemo(
		() => generateColumns<AutoRow>(definition),
		[definition]
	);

	const filterFields = React.useMemo(
		() => generateFilterFields<AutoRow>(definition),
		[definition]
	);

	const sheetFields = React.useMemo(
		() => generateSheetFields<AutoRow>(definition),
		[definition]
	);

	const defaultColumnVisibility = React.useMemo(
		() => getDefaultColumnVisibility(definition),
		[definition]
	);

	// Merge `sort` BEFORE createSchema so `defaults` cannot disagree with
	// `definition` — splicing it in afterwards left `definition.sort` present
	// while `defaults.sort` was missing.
	const filterSchema = React.useMemo(
		() => generateFilterSchema(definition, { sort: field.sort() }),
		[definition]
	);

	const adapter = useMemoryAdapter(filterSchema.definition, { id: "auto" });

	return (
		<DataTableStoreProvider adapter={adapter}>
			<DataTableAutoInner
				columns={columns}
				data={data}
				defaultColumnVisibility={defaultColumnVisibility}
				filterFields={filterFields}
				schema={filterSchema.definition}
				sheetFields={sheetFields}
			/>
		</DataTableStoreProvider>
	);
}

const noop = () => Promise.resolve();

function DataTableAutoInner({
	data,
	columns,
	filterFields,
	sheetFields,
	defaultColumnVisibility,
	schema,
}: {
	data: AutoRow[];
	columns: React.ComponentProps<typeof DataTableInfinite<AutoRow>>["columns"];
	filterFields: React.ComponentProps<
		typeof DataTableInfinite<AutoRow>
	>["filterFields"];
	sheetFields: SheetField<AutoRow>[];
	defaultColumnVisibility: Record<string, boolean>;
	schema: SchemaDefinition;
}) {
	return (
		<DataTableInfinite
			columns={columns}
			commandSlot={<DataTableFilterCommand schema={schema} tableId="auto" />}
			data={data}
			defaultColumnVisibility={defaultColumnVisibility}
			fetchNextPage={noop}
			filterFields={filterFields}
			footerSlot={
				<div className="text-muted-foreground text-sm">
					powered by{" "}
					<a
						className="text-foreground hover:text-primary"
						href="https://openstatus.dev"
						rel="noreferrer"
						target="_blank"
					>
						openstatus.dev
					</a>
				</div>
			}
			hasNextPage={false}
			isFetching={false}
			isLoading={false}
			sheetSlot={
				<AutoSheetSlot sheetFields={sheetFields} totalRows={data.length} />
			}
			tableId="auto"
			totalRowsFetched={data.length}
		/>
	);
}

function AutoSheetSlot({
	sheetFields: fields,
	totalRows,
}: {
	sheetFields: SheetField<AutoRow>[];
	totalRows: number;
}) {
	const { table, rowSelection, isLoading, filterFields } = useDataTable<
		AutoRow,
		unknown
	>();
	const selectedRowKey = Object.keys(rowSelection)?.[0];
	const selectedRow = React.useMemo(() => {
		if (isLoading && !selectedRowKey) {
			return;
		}
		return table
			.getCoreRowModel()
			.flatRows.find((row) => row.id === selectedRowKey);
	}, [selectedRowKey, isLoading, table]);

	return (
		<DataTableSheetDetails
			title={
				selectedRow ? String(Object.values(selectedRow.original)[0] ?? "") : ""
			}
			titleClassName="font-mono"
		>
			<MemoizedDataTableSheetContent
				data={selectedRow?.original}
				fields={fields}
				filterFields={filterFields}
				metadata={{
					filterRows: totalRows,
					totalRows,
					totalRowsFetched: totalRows,
				}}
				table={table}
			/>
		</DataTableSheetDetails>
	);
}
