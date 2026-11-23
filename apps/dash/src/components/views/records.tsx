"use client";

import { SearchIcon } from "lucide-react";
import { useState } from "react";
import { CodeBlock, Severity, Tabs } from "@/components/common";
import { Dialog, Select, SheetContent } from "@/components/ui/overlay";
import {
	Badge,
	Card,
	Input,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";
import { MODELS, type ModelKey } from "@/lib/catalog";
import { num, timeAgo } from "@/lib/format";
import {
	generateRecords,
	type Json,
	type JsonObject,
	type MockRecord,
} from "@/lib/records";
import type { Connection } from "@/lib/types";
import { toWire } from "@/lib/wire";

interface Column {
	className?: string;
	label: string;
	render: (r: JsonObject) => React.ReactNode;
}

function str(v: Json | undefined): string {
	if (v === null || v === undefined) {
		return "—";
	}
	if (Array.isArray(v)) {
		return v.map((x) => str(x)).join(", ");
	}
	if (typeof v === "object") {
		return JSON.stringify(v);
	}
	return String(v);
}

function get(r: JsonObject, path: string): Json | undefined {
	let cur: Json | undefined = r;
	for (const key of path.split(".")) {
		if (cur && typeof cur === "object" && !Array.isArray(cur)) {
			cur = cur[key];
		} else {
			return undefined;
		}
	}
	return cur;
}

function when(r: JsonObject, path: string): string {
	const v = get(r, path);
	return typeof v === "string" ? timeAgo(Date.parse(v)) : "—";
}

const text = (path: string, label: string, className?: string): Column => ({
	className,
	label,
	render: (r) => str(get(r, path)),
});
const mono = (path: string, label: string): Column => ({
	className: "font-mono text-code text-muted-foreground",
	label,
	render: (r) => str(get(r, path)),
});
const severity: Column = {
	label: "Severity",
	render: (r) => <Severity value={str(r.severity)} />,
};
const status: Column = {
	label: "Status",
	render: (r) => <Badge>{str(r.status).replaceAll("_", " ")}</Badge>,
};
const ago = (path: string, label: string): Column => ({
	className: "text-muted-foreground whitespace-nowrap",
	label,
	render: (r) => when(r, path),
});

const COLUMNS: Partial<Record<ModelKey, Column[]>> = {
	alerts: [
		text("title", "Title"),
		severity,
		status,
		text("entity", "Entity"),
		ago("createdAt", "Created"),
	],
	"cloud-findings": [
		text("title", "Title"),
		severity,
		text("resource.type", "Resource"),
		text("resource.region", "Region"),
		status,
	],
	"cloud-resources": [
		text("name", "Name"),
		mono("type", "Type"),
		text("cloud", "Cloud"),
		text("region", "Region"),
		{
			label: "Exposed",
			render: (r) =>
				r.internetExposed ? <Badge tone="error">Internet</Badge> : "—",
		},
	],
	"code-findings": [
		text("title", "Title"),
		severity,
		mono("type", "Type"),
		text("repository.name", "Repository"),
		status,
	],
	detections: [
		text("title", "Title"),
		severity,
		text("device.hostname", "Device"),
		status,
		ago("firstEventAt", "First event"),
	],
	devices: [
		text("hostname", "Hostname"),
		text("osVersion", "OS"),
		mono("ipv4s", "IP"),
		status,
		ago("lastSeen", "Last seen"),
	],
	groups: [
		text("name", "Name"),
		text("memberCount", "Members"),
		text("type", "Type"),
	],
	repositories: [
		text("fullName", "Repository"),
		text("language", "Language"),
		text("visibility", "Visibility"),
		text("openFindings", "Open findings"),
		ago("lastPushAt", "Last push"),
	],
	tickets: [
		mono("key", "Key"),
		text("title", "Title"),
		status,
		text("priority", "Priority"),
		ago("updatedAt", "Updated"),
	],
	users: [
		text("name", "Name"),
		text("email", "Email"),
		status,
		{
			label: "MFA",
			render: (r) =>
				get(r, "mfa.enabled") ? "Enabled" : <Badge tone="error">Off</Badge>,
		},
		ago("lastLoginAt", "Last login"),
	],
	vulnerabilities: [
		mono("cve", "CVE"),
		text("title", "Title", "max-w-80 truncate"),
		severity,
		text("asset.hostname", "Asset"),
		status,
	],
};

export function RecordsBrowser({
	conn,
	models,
	initialModel,
}: {
	conn: Connection;
	models: ModelKey[];
	initialModel?: ModelKey;
}) {
	const [model, setModel] = useState<ModelKey>(
		initialModel ?? models[0] ?? "vulnerabilities"
	);
	const [query, setQuery] = useState("");
	const [open, setOpen] = useState<MockRecord | null>(null);
	const syncing = conn.health === "SYNCING" && !conn.lastSyncAt;
	const records = syncing
		? []
		: generateRecords(
				conn.id,
				conn.provider,
				model,
				conn.domain,
				conn.lastSyncAt ?? conn.createdAt,
				100
			);
	const q = query.trim().toLowerCase();
	const visible = q
		? records.filter((r) => JSON.stringify(r.unified).toLowerCase().includes(q))
		: records;
	const columns = COLUMNS[model] ?? [mono("id", "ID")];
	const total = conn.counts[model] ?? 0;

	if (models.length === 0) {
		return (
			<p className="text-muted-foreground text-sm">
				This integration has no readable models.
			</p>
		);
	}

	return (
		<div className="grid gap-4">
			<div className="flex flex-col gap-2 sm:flex-row">
				<div className="sm:w-56">
					<Select
						ariaLabel="Model"
						onChange={(m) => {
							setModel(m);
							setQuery("");
						}}
						options={models.map((m) => ({
							label: `${MODELS[m].name} · ${num(conn.counts[m] ?? 0)}`,
							value: m,
						}))}
						value={model}
					/>
				</div>
				<div className="relative flex-1">
					<SearchIcon className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
					<Input
						aria-label="Filter records"
						className="pl-9"
						onChange={(e) => setQuery(e.target.value)}
						placeholder="Filter loaded records"
						value={query}
					/>
				</div>
			</div>
			<Card className="overflow-hidden">
				{syncing ? (
					<p className="text-muted-foreground px-5 py-12 text-center text-sm">
						The initial sync is running. Records appear when it finishes.
					</p>
				) : (
					<Table>
						<thead>
							<tr>
								{columns.map((c) => (
									<Th key={c.label}>{c.label}</Th>
								))}
							</tr>
						</thead>
						<tbody>
							{visible.map((r) => (
								<Tr
									className="cursor-pointer"
									key={r.id}
									onClick={() => setOpen(r)}
								>
									{columns.map((c, i) => (
										<Td className={c.className} key={c.label}>
											{i === 0 ? (
												<button
													className="text-left hover:underline"
													onClick={() => setOpen(r)}
													type="button"
												>
													{c.render(r.unified)}
												</button>
											) : (
												c.render(r.unified)
											)}
										</Td>
									))}
								</Tr>
							))}
						</tbody>
					</Table>
				)}
				<div className="border-border bg-ds-shell text-muted-foreground border-t px-5 py-3 text-xs">
					Showing {visible.length} of {num(total)} {MODELS[model].name} records.
					The API pages through the rest with{" "}
					<span className="font-mono">offset</span>, or{" "}
					<span className="font-mono">cursor</span> when{" "}
					<span className="font-mono">enableCursor</span> is set.
				</div>
			</Card>
			<Dialog onOpenChange={(o) => !o && setOpen(null)} open={open !== null}>
				{open ? <RecordSheet model={model} record={open} /> : null}
			</Dialog>
		</div>
	);
}

function RecordSheet({
	record,
	model,
}: {
	record: MockRecord;
	model: ModelKey;
}) {
	const [view, setView] = useState<"unified" | "raw">("unified");
	return (
		<SheetContent
			description={`${MODELS[model].name} · ${record.id}`}
			title={str(
				record.unified.title ??
					record.unified.name ??
					record.unified.hostname ??
					record.unified.fullName ??
					record.id
			)}
		>
			<div className="grid gap-4 p-6">
				<Tabs
					onChange={setView}
					tabs={[
						{ label: "Unified", value: "unified" },
						{ label: "Vendor data", value: "raw" },
					]}
					value={view}
				/>
				<p className="text-muted-foreground text-sm">
					{view === "unified"
						? "What the API returns for this record: the same fields for every vendor in the category."
						: "The vendor's original record, returned under vendor_data."}
				</p>
				<CodeBlock
					code={JSON.stringify(
						view === "unified"
							? toWire(model, record, { vendorData: false })
							: record.raw,
						null,
						2
					)}
					json
				/>
			</div>
		</SheetContent>
	);
}
