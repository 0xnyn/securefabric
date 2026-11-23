"use client";

import { unwrap } from "@securefabric/client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { PageBody, PageHeader } from "@/components/common";
import {
	ConnectorLogo,
	errorText,
	QueryState,
	Section,
} from "@/components/kit";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import {
	Badge,
	Card,
	Input,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { Connector } from "@/lib/types";

const STATUS_TONE = { beta: "accent", deprecated: "warn", ga: "ok" } as const;

function useConnectors() {
	return useQuery({
		queryFn: () => unwrap(api.GET("/v1/connectors")),
		queryKey: ["connectors"],
	});
}

export function CatalogView() {
	const connectors = useConnectors();
	const href = useHref();
	const [q, setQ] = useState("");
	const items = (connectors.data ?? []).filter((c) =>
		`${c.name} ${c.id} ${c.categories.join(" ")}`
			.toLowerCase()
			.includes(q.toLowerCase())
	);
	return (
		<>
			<PageHeader
				actions={
					<Input
						className="w-64"
						onChange={(e) => setQ(e.target.value)}
						placeholder="Search connectors"
						value={q}
					/>
				}
				description="Generated from each connector's manifest: auth, streams, permissions and capabilities."
				title="Catalog"
			/>
			<PageBody>
				<QueryState
					empty={{
						description: "Try another search.",
						title: "No connectors",
						when: items.length === 0,
					}}
					query={connectors}
				>
					<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
						{items.map((c) => (
							<Link
								className="block"
								href={href(`/catalog/${c.id}`)}
								key={c.id}
							>
								<Card className="hover:border-ds-accent/50 grid h-full gap-3 p-5 transition-colors">
									<div className="flex items-center gap-3">
										<ConnectorLogo id={c.id} logo={c.logo_url} size={36} />
										<div className="grid min-w-0">
											<span className="truncate font-medium">{c.name}</span>
											<span className="text-muted-foreground font-mono text-xs">
												{c.id}
											</span>
										</div>
										<Badge
											className="ml-auto"
											tone={
												STATUS_TONE[c.status as keyof typeof STATUS_TONE] ??
												"neutral"
											}
										>
											{c.status}
										</Badge>
									</div>
									<p className="text-muted-foreground line-clamp-2 text-sm">
										{c.description}
									</p>
									<div className="flex flex-wrap gap-1.5">
										<Badge>{c.auth.mode as string}</Badge>
										{c.data_types.map((d) => (
											<Badge key={d} tone="accent">
												{d.replaceAll("_", " ")}
											</Badge>
										))}
										<Badge>{c.streams.length} streams</Badge>
									</div>
								</Card>
							</Link>
						))}
					</div>
				</QueryState>
			</PageBody>
		</>
	);
}

function capabilityRows(c: Connector) {
	const rows: {
		stream: string;
		field: string;
		supported: boolean;
		notes: string | null;
	}[] = [];
	for (const s of c.streams as Record<string, unknown>[]) {
		for (const [field, cap] of Object.entries(
			(s.capabilities as
				| Record<string, { supported: boolean; notes?: string | null }>
				| undefined) ?? {}
		)) {
			rows.push({
				field,
				notes: cap.notes ?? null,
				stream: String(s.name),
				supported: cap.supported,
			});
		}
	}
	return rows;
}

export function ConnectorView({ id }: { id: string }) {
	const connector = useQuery({
		queryFn: () =>
			unwrap(
				api.GET("/v1/connectors/{connector_id}", {
					params: { path: { connector_id: id } },
				})
			),
		queryKey: ["connectors", id],
	});
	const { client, env } = useEnv();
	const router = useRouter();
	const href = useHref();
	const queryClient = useQueryClient();
	const integrations = useQuery({
		queryFn: () => unwrap(client.GET("/v1/integrations")),
		queryKey: ["integrations", env.id],
	});
	const existing = integrations.data?.find((i) => i.connector_id === id);
	const enable = useMutation({
		mutationFn: () =>
			unwrap(client.POST("/v1/integrations", { body: { connector_id: id } })),
		onError: (e) =>
			toast.error("Couldn't enable", { description: errorText(e) }),
		onSuccess: async (i) => {
			await queryClient.invalidateQueries({
				queryKey: ["integrations", env.id],
			});
			toast.success(`${i.display_name} enabled`);
			router.push(href(`/integrations/${i.id}`));
		},
	});
	const c = connector.data;
	return (
		<QueryState query={connector}>
			{c ? (
				<>
					<PageHeader
						actions={
							existing ? (
								<Button
									render={<Link href={href(`/integrations/${existing.id}`)} />}
									variant="outline"
								>
									Configure integration
								</Button>
							) : (
								<Button
									disabled={enable.isPending}
									onClick={() => enable.mutate()}
									variant="primary"
								>
									Enable in {env.name}
								</Button>
							)
						}
						description={c.description}
						title={
							<span className="flex items-center gap-3">
								<ConnectorLogo id={c.id} logo={c.logo_url} size={32} />
								{c.name}
							</span>
						}
					/>
					<PageBody className="grid gap-8">
						<Section
							description="How a connection authenticates"
							title="Authentication"
						>
							<Card className="grid gap-2 p-5 text-sm">
								<div>
									Mode <Badge>{c.auth.mode as string}</Badge> · connect{" "}
									<Badge>{c.auth.connect as string}</Badge>
									{c.auth.vendor_app === "none" ? null : (
										<>
											{" "}
											· vendor app <Badge>{c.auth.vendor_app as string}</Badge>
										</>
									)}
								</div>
								{c.regions.length ? (
									<div className="text-muted-foreground">
										Regions:{" "}
										{c.regions
											.map((r) => `${r.label ?? r.id} (${r.api_base})`)
											.join(" · ")}
									</div>
								) : null}
							</Card>
						</Section>
						<Section
							description="What to grant in the vendor (the connect UI shows this guide)"
							title="Permissions"
						>
							<Card>
								<Table>
									<thead>
										<Tr>
											<Th>Permission</Th>
											<Th>Access</Th>
											<Th>Used by</Th>
										</Tr>
									</thead>
									<tbody>
										{c.permissions.map((p) => (
											<Tr key={`${String(p.name)}:${String(p.access)}`}>
												<Td>
													{String(p.name)}
													{p.optional ? (
														<Badge className="ml-2">optional</Badge>
													) : null}
												</Td>
												<Td>{String(p.access)}</Td>
												<Td className="text-muted-foreground">
													{[
														...((p.streams as string[] | undefined) ?? []),
														...((p.actions as string[] | undefined) ?? []),
													].join(", ")}
												</Td>
											</Tr>
										))}
									</tbody>
								</Table>
							</Card>
						</Section>
						<Section title="Streams">
							<Card>
								<Table>
									<thead>
										<Tr>
											<Th>Stream</Th>
											<Th>Object</Th>
											<Th>Mode</Th>
											<Th>Deletion</Th>
											<Th>Interval</Th>
											<Th>Natural key</Th>
										</Tr>
									</thead>
									<tbody>
										{(c.streams as Record<string, unknown>[]).map((s) => {
											const iv = s.interval as {
												default: number;
												min: number;
												max: number;
											};
											return (
												<Tr key={String(s.name)}>
													<Td>
														<div className="font-medium">{String(s.title)}</div>
														<div className="text-muted-foreground font-mono text-xs">
															{String(s.name)}
														</div>
													</Td>
													<Td>{String(s.object).replaceAll("_", " ")}</Td>
													<Td>{String(s.sync_mode)}</Td>
													<Td>{String(s.deletion).replaceAll("_", " ")}</Td>
													<Td className="whitespace-nowrap">
														{iv.default / 60} min ({iv.min / 60}–{iv.max / 60})
													</Td>
													<Td className="font-mono text-xs">
														{String(s.natural_key)}
													</Td>
												</Tr>
											);
										})}
									</tbody>
								</Table>
							</Card>
						</Section>
						<Section
							description="Fields this connector can honestly fill (tri-state fields stay null otherwise)"
							title="Capabilities"
						>
							<Card>
								<Table>
									<thead>
										<Tr>
											<Th>Stream</Th>
											<Th>Field</Th>
											<Th>Supported</Th>
											<Th>Notes</Th>
										</Tr>
									</thead>
									<tbody>
										{capabilityRows(c).map((r) => (
											<Tr key={`${r.stream}.${r.field}`}>
												<Td className="font-mono text-xs">{r.stream}</Td>
												<Td>{r.field}</Td>
												<Td>
													<Badge tone={r.supported ? "ok" : "neutral"}>
														{r.supported ? "yes" : "no"}
													</Badge>
												</Td>
												<Td className="text-muted-foreground">
													{r.notes ?? ""}
												</Td>
											</Tr>
										))}
									</tbody>
								</Table>
							</Card>
						</Section>
					</PageBody>
				</>
			) : null}
		</QueryState>
	);
}
