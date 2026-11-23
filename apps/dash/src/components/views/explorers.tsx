"use client";

import { unwrap } from "@securefabric/client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownIcon, ArrowUpIcon, ExternalLinkIcon } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { KeyValue, PageBody, PageHeader } from "@/components/common";
import {
	errorText,
	JsonBlock,
	Pager,
	QueryState,
	SeverityLabel,
	StatusBadge,
	useCursorStack,
	When,
} from "@/components/kit";
import { useEnv } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { Dialog, Select, SheetContent } from "@/components/ui/overlay";
import {
	Badge,
	Card,
	Field,
	Input,
	Table,
	Td,
	Textarea,
	Th,
	Tr,
} from "@/components/ui/primitives";
import { useDebounce } from "@/hooks/use-debounce";
import {
	FINDING_STATE_TONES,
	FINDING_STATES,
	FINDING_TYPES,
	type Finding,
	RESOURCE_TYPES,
	type Resource,
	SEVERITIES,
} from "@/lib/types";

/** Exactly one of these scopes every data read (API-03). */
export type Scope = { connectionId: string } | { organizationId: string };

export function scopeHeaders(scope: Scope): {
	"X-CONNECTION-ID"?: string;
	"X-ORGANIZATION-ID"?: string;
} {
	return "connectionId" in scope
		? { "X-CONNECTION-ID": scope.connectionId }
		: { "X-ORGANIZATION-ID": scope.organizationId };
}

function scopeKey(scope: Scope): string {
	return "connectionId" in scope
		? `c:${scope.connectionId}`
		: `o:${scope.organizationId}`;
}

const ANY = "any";

function options(values: readonly string[], anyLabel: string) {
	return [
		{ label: anyLabel, value: ANY },
		...values.map((v) => ({ label: v.toLowerCase(), value: v })),
	];
}

/** A sortable column header: click toggles asc/desc, sent as `sort=field:dir`. */
function SortTh({
	field,
	label,
	sort,
	onSort,
}: {
	field: string;
	label: string;
	sort: string;
	onSort: (s: string) => void;
}) {
	const [f, dir] = sort.split(":");
	const active = f === field;
	return (
		<Th>
			<button
				className="hover:text-foreground inline-flex items-center gap-1"
				onClick={() =>
					onSort(`${field}:${active && dir === "desc" ? "asc" : "desc"}`)
				}
				type="button"
			>
				{label}
				{active && dir === "desc" ? <ArrowDownIcon className="size-3" /> : null}
				{active && dir !== "desc" ? <ArrowUpIcon className="size-3" /> : null}
			</button>
		</Th>
	);
}

// ---------------------------------------------------------------------------
// Findings

export function FindingsExplorer({ scope }: { scope: Scope }) {
	const { client, env } = useEnv();
	const pages = useCursorStack();
	const [severity, setSeverity] = useState(ANY);
	const [state, setState] = useState(ANY);
	const [type, setType] = useState(ANY);
	const [cveInput, setCveInput] = useState("");
	const cve = useDebounce(cveInput.trim(), 300);
	const [sort, setSort] = useState("severity:desc");
	const [selected, setSelected] = useState<Finding | null>(null);
	const findings = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/vulnerability_findings", {
					params: {
						header: scopeHeaders(scope),
						query: {
							cursor: pages.cursor,
							cveId: cve || undefined,
							limit: 50,
							severity: severity === ANY ? undefined : severity,
							sort,
							state: state === ANY ? undefined : state,
							type: type === ANY ? undefined : type,
						},
					},
				})
			),
		queryKey: [
			"findings",
			env.id,
			scopeKey(scope),
			severity,
			state,
			type,
			cve,
			sort,
			pages.cursor,
		],
	});
	const filter =
		<T,>(fn: (v: T) => void) =>
		(v: T) => {
			pages.reset();
			fn(v);
		};
	return (
		<div className="grid gap-3">
			<div className="flex flex-wrap gap-2">
				<Select
					ariaLabel="Severity"
					className="w-36"
					onChange={filter(setSeverity)}
					options={options(SEVERITIES, "Any severity")}
					size="sm"
					value={severity}
				/>
				<Select
					ariaLabel="State"
					className="w-36"
					onChange={filter(setState)}
					options={options(FINDING_STATES, "Any state")}
					size="sm"
					value={state}
				/>
				<Select
					ariaLabel="Type"
					className="w-36"
					onChange={filter(setType)}
					options={options(FINDING_TYPES, "Any type")}
					size="sm"
					value={type}
				/>
				<Input
					className="h-7 w-44 text-xs"
					onChange={(e) => {
						pages.reset();
						setCveInput(e.target.value);
					}}
					placeholder="CVE-2024-…"
					value={cveInput}
				/>
			</div>
			<QueryState
				empty={{
					description:
						"Nothing matches these filters, or the first sync hasn't finished.",
					title: "No findings",
					when: (findings.data?.items.length ?? 0) === 0,
				}}
				query={findings}
			>
				<Card>
					<Table>
						<thead>
							<Tr>
								<SortTh
									field="severity"
									label="Severity"
									onSort={filter(setSort)}
									sort={sort}
								/>
								<Th>Finding</Th>
								<Th>Type</Th>
								<Th>State</Th>
								<SortTh
									field="last_seen"
									label="Last seen"
									onSort={filter(setSort)}
									sort={sort}
								/>
								<SortTh
									field="updated_at"
									label="Updated"
									onSort={filter(setSort)}
									sort={sort}
								/>
							</Tr>
						</thead>
						<tbody>
							{findings.data?.items.map((f) => (
								<Tr
									className="hover:bg-muted/40 cursor-pointer"
									key={f.id}
									onClick={() => setSelected(f)}
								>
									<Td>
										<SeverityLabel value={f.severity} />
									</Td>
									<Td className="max-w-md">
										<div className="truncate font-medium">
											{f.title ?? f.id}
										</div>
										{f.cve_ids.length ? (
											<div className="text-muted-foreground truncate font-mono text-xs">
												{f.cve_ids.join(", ")}
											</div>
										) : null}
									</Td>
									<Td className="text-xs">{f.type.toLowerCase()}</Td>
									<Td>
										<StatusBadge tones={FINDING_STATE_TONES} value={f.state} />
									</Td>
									<Td>
										<When value={f.last_seen} />
									</Td>
									<Td>
										<When value={f.updated_at} />
									</Td>
								</Tr>
							))}
						</tbody>
					</Table>
				</Card>
				<Pager
					count={findings.data?.items.length}
					hasNext={Boolean(findings.data?.next_cursor)}
					onNext={() => pages.next(findings.data?.next_cursor)}
					onPrev={pages.prev}
					page={pages.page}
				/>
			</QueryState>
			<Dialog
				onOpenChange={(o) => (o ? null : setSelected(null))}
				open={selected !== null}
			>
				{selected ? <FindingSheet finding={selected} /> : null}
			</Dialog>
		</div>
	);
}

/** Tri-state fields: null means the connector can't say (NORM-07). */
function triState(v: boolean | null): string {
	if (v === null) {
		return "unknown";
	}
	return v ? "yes" : "no";
}

const REASONS = [
	"false_positive",
	"accepted_risk",
	"test_code",
	"revoked",
] as const;

function FindingSheet({ finding }: { finding: Finding }) {
	const { client, env } = useEnv();
	const queryClient = useQueryClient();
	const headers = { "X-CONNECTION-ID": finding.connection_id };
	const detail = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/vulnerability_findings/{finding_id}", {
					params: { header: headers, path: { finding_id: finding.id } },
				})
			),
		queryKey: ["finding", env.id, finding.id],
	});
	const history = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/vulnerability_findings/{finding_id}/history", {
					params: { header: headers, path: { finding_id: finding.id } },
				})
			),
		queryKey: ["finding-history", env.id, finding.id],
	});
	const [target, setTarget] = useState<"OPEN" | "IGNORED" | "CLOSED">(
		"IGNORED"
	);
	const [reason, setReason] = useState<string>("false_positive");
	const [comment, setComment] = useState("");
	const act = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/vulnerability_findings/{finding_id}/actions", {
					body: {
						action: "set_state",
						comment: comment || null,
						reason: target === "OPEN" ? null : reason,
						state: target,
					},
					headers: { "Idempotency-Key": crypto.randomUUID() },
					params: { header: headers, path: { finding_id: finding.id } },
				})
			),
		onError: (e) =>
			toast.error("The vendor didn't accept that", {
				description: errorText(e),
			}),
		onSuccess: async (a) => {
			toast.success("Action requested", {
				description: `Status ${a.status.toLowerCase()}. The finding is re-fetched from the vendor once it completes.`,
			});
			await queryClient.invalidateQueries({ queryKey: ["findings", env.id] });
		},
	});
	const f = detail.data ?? finding;
	const vendorUrl = (f.vendor_attributes as { url?: string } | null)?.url;
	return (
		<SheetContent
			actions={
				vendorUrl ? (
					<Button
						render={<a href={vendorUrl} rel="noreferrer" target="_blank" />}
						size="sm"
						variant="outline"
					>
						Open in vendor <ExternalLinkIcon />
					</Button>
				) : null
			}
			description={<span className="font-mono text-xs">{f.id}</span>}
			title={f.title ?? "Finding"}
		>
			<div className="grid gap-6 p-6">
				<KeyValue
					items={[
						{ label: "Severity", value: <SeverityLabel value={f.severity} /> },
						{
							label: "State",
							value: (
								<StatusBadge tones={FINDING_STATE_TONES} value={f.state} />
							),
						},
						{ label: "Type", value: f.type.toLowerCase() },
						{
							label: "Has fix",
							value: triState(f.has_fix),
						},
						{
							label: "Exploitable",
							value: triState(f.exploitable),
						},
						{ label: "Reachability", value: f.reachability ?? "unknown" },
						{ label: "First seen", value: <When value={f.first_seen} /> },
						{ label: "Last seen", value: <When value={f.last_seen} /> },
						{ label: "CVEs", value: f.cve_ids.join(", ") || "—" },
						{
							label: "Connection",
							value: (
								<span className="font-mono text-xs">{f.connection_id}</span>
							),
						},
					]}
				/>
				{f.description ? (
					<p className="text-sm whitespace-pre-wrap">{f.description}</p>
				) : null}
				{f.remediation ? (
					<div className="grid gap-1">
						<h3 className="text-sm font-semibold">Remediation</h3>
						<p className="text-muted-foreground text-sm whitespace-pre-wrap">
							{f.remediation}
						</p>
					</div>
				) : null}
				<div className="grid gap-2">
					<h3 className="text-sm font-semibold">Change state at the vendor</h3>
					<div className="grid grid-cols-2 gap-2">
						<Select
							ariaLabel="New state"
							onChange={setTarget}
							options={[
								{ label: "Open", value: "OPEN" },
								{ label: "Ignored", value: "IGNORED" },
								{ label: "Closed", value: "CLOSED" },
							]}
							size="sm"
							value={target}
						/>
						<Select
							ariaLabel="Reason"
							onChange={setReason}
							options={REASONS.map((r) => ({
								label: r.replace("_", " "),
								value: r,
							}))}
							size="sm"
							value={reason}
						/>
					</div>
					<Field htmlFor="action-comment" label="Comment (optional)">
						<Textarea
							id="action-comment"
							onChange={(e) => setComment(e.target.value)}
							rows={2}
							value={comment}
						/>
					</Field>
					<div>
						<Button
							disabled={act.isPending}
							onClick={() => act.mutate()}
							size="sm"
							variant="primary"
						>
							Request change
						</Button>
					</div>
				</div>
				<div className="grid gap-2">
					<h3 className="text-sm font-semibold">State history</h3>
					<QueryState query={history} rows={2}>
						{(history.data ?? []).length === 0 ? (
							<p className="text-muted-foreground text-sm">
								No state changes recorded.
							</p>
						) : (
							<ol className="grid gap-1 text-sm">
								{history.data?.map((h) => (
									<li
										className="flex items-center gap-2"
										key={`${h.at}-${h.to_state}`}
									>
										<When className="text-muted-foreground w-28" value={h.at} />
										<span>
											{h.from_state ?? "new"} → <strong>{h.to_state}</strong>
										</span>
										<Badge>{h.source}</Badge>
									</li>
								))}
							</ol>
						)}
					</QueryState>
				</div>
				<div className="grid gap-2">
					<h3 className="text-sm font-semibold">Vendor attributes</h3>
					<JsonBlock value={f.vendor_attributes} />
				</div>
				{f.vulnerabilities.length ? (
					<div className="grid gap-2">
						<h3 className="text-sm font-semibold">Vulnerabilities</h3>
						<JsonBlock value={f.vulnerabilities} />
					</div>
				) : null}
				{f.resources.length ? (
					<div className="grid gap-2">
						<h3 className="text-sm font-semibold">Resources</h3>
						<JsonBlock value={f.resources} />
					</div>
				) : null}
			</div>
		</SheetContent>
	);
}

// ---------------------------------------------------------------------------
// Resources

export function ResourcesExplorer({ scope }: { scope: Scope }) {
	const { client, env } = useEnv();
	const pages = useCursorStack();
	const [type, setType] = useState(ANY);
	const [nameInput, setNameInput] = useState("");
	const name = useDebounce(nameInput.trim(), 300);
	const [sort, setSort] = useState("updated_at:desc");
	const [selected, setSelected] = useState<Resource | null>(null);
	const resources = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/resources", {
					params: {
						header: scopeHeaders(scope),
						query: {
							cursor: pages.cursor,
							limit: 50,
							name: name || undefined,
							sort,
							type: type === ANY ? undefined : type,
						},
					},
				})
			),
		queryKey: [
			"resources",
			env.id,
			scopeKey(scope),
			type,
			name,
			sort,
			pages.cursor,
		],
	});
	const filter =
		<T,>(fn: (v: T) => void) =>
		(v: T) => {
			pages.reset();
			fn(v);
		};
	return (
		<div className="grid gap-3">
			<div className="flex flex-wrap gap-2">
				<Select
					ariaLabel="Type"
					className="w-40"
					onChange={filter(setType)}
					options={options(RESOURCE_TYPES, "Any type")}
					size="sm"
					value={type}
				/>
				<Input
					className="h-7 w-52 text-xs"
					onChange={(e) => {
						pages.reset();
						setNameInput(e.target.value);
					}}
					placeholder="Name contains…"
					value={nameInput}
				/>
			</div>
			<QueryState
				empty={{
					description: "Nothing matches, or the first sync hasn't finished.",
					title: "No resources",
					when: (resources.data?.items.length ?? 0) === 0,
				}}
				query={resources}
			>
				<Card>
					<Table>
						<thead>
							<Tr>
								<Th>Name</Th>
								<Th>Type</Th>
								<Th>Vendor</Th>
								<Th>State</Th>
								<SortTh
									field="last_seen"
									label="Last seen"
									onSort={filter(setSort)}
									sort={sort}
								/>
								<SortTh
									field="updated_at"
									label="Updated"
									onSort={filter(setSort)}
									sort={sort}
								/>
							</Tr>
						</thead>
						<tbody>
							{resources.data?.items.map((r) => (
								<Tr
									className="hover:bg-muted/40 cursor-pointer"
									key={r.id}
									onClick={() => setSelected(r)}
								>
									<Td className="max-w-md truncate font-medium">
										{r.name}
										{r.is_stub ? <Badge className="ml-2">stub</Badge> : null}
									</Td>
									<Td className="text-xs">{r.type.toLowerCase()}</Td>
									<Td className="text-xs">{r.vendor}</Td>
									<Td className="text-xs">{r.state.toLowerCase()}</Td>
									<Td>
										<When value={r.last_seen} />
									</Td>
									<Td>
										<When value={r.updated_at} />
									</Td>
								</Tr>
							))}
						</tbody>
					</Table>
				</Card>
				<Pager
					count={resources.data?.items.length}
					hasNext={Boolean(resources.data?.next_cursor)}
					onNext={() => pages.next(resources.data?.next_cursor)}
					onPrev={pages.prev}
					page={pages.page}
				/>
			</QueryState>
			<Dialog
				onOpenChange={(o) => (o ? null : setSelected(null))}
				open={selected !== null}
			>
				{selected ? (
					<SheetContent
						actions={
							selected.url ? (
								<Button
									render={
										<a href={selected.url} rel="noreferrer" target="_blank" />
									}
									size="sm"
									variant="outline"
								>
									Open <ExternalLinkIcon />
								</Button>
							) : null
						}
						description={
							<span className="font-mono text-xs">{selected.id}</span>
						}
						title={selected.name}
					>
						<div className="grid gap-6 p-6">
							<KeyValue
								items={[
									{ label: "Type", value: selected.type },
									{ label: "State", value: selected.state },
									{ label: "Vendor", value: selected.vendor },
									{
										label: "First seen",
										value: <When value={selected.first_seen} />,
									},
									{
										label: "Last seen",
										value: <When value={selected.last_seen} />,
									},
									{
										label: "Connection",
										value: (
											<span className="font-mono text-xs">
												{selected.connection_id}
											</span>
										),
									},
								]}
							/>
							{selected.data ? (
								<div className="grid gap-2">
									<h3 className="text-sm font-semibold">Data</h3>
									<JsonBlock value={selected.data} />
								</div>
							) : null}
							<div className="grid gap-2">
								<h3 className="text-sm font-semibold">Vendor attributes</h3>
								<JsonBlock value={selected.vendor_attributes} />
							</div>
						</div>
					</SheetContent>
				) : null}
			</Dialog>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Pages: pick the organization (or a connection) to scope to.

function ScopePicker({
	children,
}: {
	children: (scope: Scope) => React.ReactNode;
}) {
	const { client, env } = useEnv();
	const params = useSearchParams();
	const orgs = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/organizations", { params: { query: { limit: 500 } } })
			),
		queryKey: ["organizations", env.id, "all"],
	});
	const [org, setOrg] = useState<string | null>(params.get("org"));
	const connection = params.get("connection");
	const current = org ?? orgs.data?.items[0]?.id ?? null;
	if (connection) {
		return <>{children({ connectionId: connection })}</>;
	}
	return (
		<QueryState
			empty={{
				description:
					"Data is read per organization or connection. Add an organization and connect it first.",
				title: "No organizations yet",
				when: (orgs.data?.items.length ?? 0) === 0,
			}}
			query={orgs}
		>
			<div className="grid gap-4">
				<Field label="Organization">
					<Select
						ariaLabel="Organization"
						className="w-72"
						onChange={setOrg}
						options={(orgs.data?.items ?? []).map((o) => ({
							label: o.name,
							value: o.id,
						}))}
						value={current ?? ""}
					/>
				</Field>
				{current ? (
					<div key={current}>{children({ organizationId: current })}</div>
				) : null}
			</div>
		</QueryState>
	);
}

export function FindingsView() {
	return (
		<>
			<PageHeader
				description="Unified vulnerability findings, read with X-ORGANIZATION-ID. Filters and sort run on the server; paging is keyset."
				title="Findings"
			/>
			<PageBody>
				<ScopePicker>
					{(scope) => <FindingsExplorer scope={scope} />}
				</ScopePicker>
			</PageBody>
		</>
	);
}

export function ResourcesView() {
	return (
		<>
			<PageHeader
				description="Repositories, images, hosts and other assets the connectors found."
				title="Resources"
			/>
			<PageBody>
				<ScopePicker>
					{(scope) => <ResourcesExplorer scope={scope} />}
				</ScopePicker>
			</PageBody>
		</>
	);
}
