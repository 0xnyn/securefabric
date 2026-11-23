"use client";

import { unwrap } from "@securefabric/client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Fragment, useState } from "react";
import { toast } from "sonner";
import { KeyValue, PageBody, PageHeader } from "@/components/common";
import {
	errorText,
	JsonBlock,
	QueryState,
	Section,
	When,
} from "@/components/kit";
import { useEnv } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/overlay";
import {
	Badge,
	Card,
	EmptyState,
	Field,
	Input,
	Table,
	Td,
	Textarea,
	Th,
	Tr,
} from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { SETTINGS_SECTIONS, settingsSection } from "@/lib/nav";

const WHITESPACE = /\s+/u;

interface ConnectUi {
	accent_color: string;
	logo_url: string | null;
	name: string | null;
	theme: "system" | "light" | "dark";
}

function useSaveEnv() {
	const { client } = useEnv();
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: (body: { name?: string; settings?: Record<string, unknown> }) =>
			unwrap(client.PATCH("/v1/environments/current", { body })),
		onError: (e) => toast.error("Couldn't save", { description: errorText(e) }),
		onSuccess: async () => {
			toast.success("Saved");
			await queryClient.invalidateQueries({ queryKey: ["environments"] });
		},
	});
}

export function SettingsView() {
	const { env } = useEnv();
	const params = useSearchParams();
	const section = settingsSection(params.get("tab"));
	const meta = SETTINGS_SECTIONS.find((s) => s.value === section);
	return (
		<>
			<PageHeader
				description={meta?.description}
				title={`${meta?.label ?? "Settings"} · ${env.name}`}
			/>
			<PageBody className="max-w-3xl">
				{section === "general" ? <General /> : null}
				{section === "connect" ? <ConnectBranding /> : null}
				{section === "team" ? <Team /> : null}
				{section === "audit" ? <Audit /> : null}
			</PageBody>
		</>
	);
}

function General() {
	const { env } = useEnv();
	const save = useSaveEnv();
	const [name, setName] = useState(env.name);
	const [origins, setOrigins] = useState(
		(
			(env.settings.allowed_redirect_origins as string[] | undefined) ?? []
		).join("\n")
	);
	return (
		<div className="grid gap-8">
			<Card className="p-5">
				<KeyValue
					items={[
						{
							label: "Environment id",
							value: <span className="font-mono text-xs">{env.id}</span>,
						},
						{
							label: "Slug",
							value: <span className="font-mono">{env.slug}</span>,
						},
						{ label: "Production", value: env.is_production ? "yes" : "no" },
						{ label: "Created", value: <When value={env.created_at} /> },
					]}
				/>
			</Card>
			<Section title="Name">
				<div className="flex gap-2">
					<Input
						className="max-w-sm"
						onChange={(e) => setName(e.target.value)}
						value={name}
					/>
					<Button
						disabled={save.isPending || !name.trim()}
						onClick={() => save.mutate({ name: name.trim() })}
						variant="primary"
					>
						Save
					</Button>
				</div>
			</Section>
			<Section
				description="Connect sessions may only redirect to these origins (redirect_success / redirect_error). One per line, e.g. https://app.example.com."
				title="Allowed redirect origins"
			>
				<Textarea
					className="font-mono text-xs"
					onChange={(e) => setOrigins(e.target.value)}
					rows={4}
					value={origins}
				/>
				<div>
					<Button
						disabled={save.isPending}
						onClick={() =>
							save.mutate({
								settings: {
									allowed_redirect_origins: origins
										.split(WHITESPACE)
										.map((o) => o.trim())
										.filter(Boolean),
								},
							})
						}
						variant="primary"
					>
						Save origins
					</Button>
				</div>
			</Section>
		</div>
	);
}

function ConnectBranding() {
	const { env } = useEnv();
	const save = useSaveEnv();
	const initial = (env.settings.connect_ui ?? {}) as Partial<ConnectUi>;
	const [ui, setUi] = useState<ConnectUi>({
		accent_color: initial.accent_color ?? "#4f46e5",
		logo_url: initial.logo_url ?? null,
		name: initial.name ?? null,
		theme: initial.theme ?? "system",
	});
	return (
		<div className="grid gap-6 md:grid-cols-[1fr_16rem]">
			<div className="grid gap-4">
				<Field
					help="Shown to your customers in the hosted connect flow"
					htmlFor="cu-name"
					label="Display name"
				>
					<Input
						id="cu-name"
						onChange={(e) => setUi({ ...ui, name: e.target.value || null })}
						value={ui.name ?? ""}
					/>
				</Field>
				<Field help="HTTPS image URL" htmlFor="cu-logo" label="Logo URL">
					<Input
						id="cu-logo"
						onChange={(e) => setUi({ ...ui, logo_url: e.target.value || null })}
						value={ui.logo_url ?? ""}
					/>
				</Field>
				<Field htmlFor="cu-accent" label="Accent colour">
					<div className="flex gap-2">
						<input
							aria-label="Accent colour picker"
							className="h-8 w-10 cursor-pointer rounded border"
							onChange={(e) => setUi({ ...ui, accent_color: e.target.value })}
							type="color"
							value={ui.accent_color}
						/>
						<Input
							className="w-32 font-mono"
							id="cu-accent"
							onChange={(e) => setUi({ ...ui, accent_color: e.target.value })}
							value={ui.accent_color}
						/>
					</div>
				</Field>
				<Field label="Theme">
					<Select
						onChange={(v) => setUi({ ...ui, theme: v })}
						options={[
							{ label: "Follow the system", value: "system" },
							{ label: "Light", value: "light" },
							{ label: "Dark", value: "dark" },
						]}
						value={ui.theme}
					/>
				</Field>
				<div>
					<Button
						disabled={save.isPending}
						onClick={() => save.mutate({ settings: { connect_ui: ui } })}
						variant="primary"
					>
						Save branding
					</Button>
				</div>
			</div>
			<Card className="grid content-start gap-3 p-5">
				<span className="text-muted-foreground text-xs">Preview</span>
				<div className="flex items-center gap-2">
					{ui.logo_url ? (
						// biome-ignore lint/performance/noImgElement: arbitrary customer URL, not optimizable
						<img
							alt=""
							className="size-6 rounded"
							height={24}
							src={ui.logo_url}
							width={24}
						/>
					) : null}
					<span className="font-semibold">{ui.name ?? env.name}</span>
				</div>
				<p className="text-muted-foreground text-xs">
					Connect your tools to share security findings.
				</p>
				<button
					className="rounded-md px-3 py-1.5 text-sm font-medium text-white"
					style={{ background: ui.accent_color }}
					type="button"
				>
					Continue
				</button>
			</Card>
		</div>
	);
}

/** Members and the audit log belong to signed-in users, not API keys. */
function SessionOnly({ what }: { what: string }) {
	return (
		<EmptyState
			description={`The dashboard is using SF_DEV_API_KEY. ${what} is available when you sign in with WorkOS.`}
			title="Sign in to see this"
		/>
	);
}

function Team() {
	const { me, devMode } = useEnv();
	if (devMode) {
		return <SessionOnly what="Team management" />;
	}
	return <TeamMembers me={me} />;
}

function TeamMembers({ me }: { me: ReturnType<typeof useEnv>["me"] }) {
	const queryClient = useQueryClient();
	const members = useQuery({
		queryFn: () => unwrap(api.GET("/v1/members")),
		queryKey: ["members"],
	});
	const [email, setEmail] = useState("");
	const [role, setRole] = useState<"admin" | "developer" | "support">(
		"developer"
	);
	const invite = useMutation({
		mutationFn: () =>
			unwrap(api.POST("/v1/members", { body: { email, role } })),
		onError: (e) =>
			toast.error("Couldn't invite", { description: errorText(e) }),
		onSuccess: async (i) => {
			toast.success(`Invited ${i.email}`, { description: i.state });
			setEmail("");
			await queryClient.invalidateQueries({ queryKey: ["members"] });
		},
	});
	const remove = useMutation({
		mutationFn: (id: string) =>
			unwrap(
				api.DELETE("/v1/members/{user_id}", {
					params: { path: { user_id: id } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't remove", { description: errorText(e) }),
		onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members"] }),
	});
	return (
		<div className="grid gap-6">
			<Section
				description="Members belong to the account and see every environment."
				title="Invite"
			>
				<div className="flex flex-wrap gap-2">
					<Input
						className="w-72"
						onChange={(e) => setEmail(e.target.value)}
						placeholder="teammate@example.com"
						type="email"
						value={email}
					/>
					<Select
						ariaLabel="Role"
						className="w-36"
						onChange={setRole}
						options={[
							{ label: "Admin", value: "admin" },
							{ label: "Developer", value: "developer" },
							{ label: "Support", value: "support" },
						]}
						value={role}
					/>
					<Button
						disabled={!email || invite.isPending}
						onClick={() => invite.mutate()}
						variant="primary"
					>
						Invite
					</Button>
				</div>
			</Section>
			<QueryState
				empty={{
					description:
						me.kind === "api_key"
							? "Members are managed by signed-in users, not API keys."
							: "Invite your team.",
					title: "No members",
					when: (members.data ?? []).length === 0,
				}}
				query={members}
			>
				<Card>
					<Table>
						<thead>
							<Tr>
								<Th>Member</Th>
								<Th>Role</Th>
								<Th>Joined</Th>
								<Th />
							</Tr>
						</thead>
						<tbody>
							{members.data?.map((m) => (
								<Tr key={m.user_id}>
									<Td>
										<div className="font-medium">{m.name ?? m.email}</div>
										<div className="text-muted-foreground text-xs">
											{m.email}
										</div>
									</Td>
									<Td>
										<Badge>{m.role}</Badge>
									</Td>
									<Td>
										<When value={m.joined_at} />
									</Td>
									<Td className="text-right">
										{m.user_id === me.actor_id ? null : (
											<Button
												onClick={() => remove.mutate(m.user_id)}
												size="xs"
												variant="ghost"
											>
												Remove
											</Button>
										)}
									</Td>
								</Tr>
							))}
						</tbody>
					</Table>
				</Card>
			</QueryState>
		</div>
	);
}

function Audit() {
	const { devMode } = useEnv();
	return devMode ? <SessionOnly what="The audit log" /> : <AuditLog />;
}

function AuditLog() {
	const { client, env } = useEnv();
	const [open, setOpen] = useState<string | null>(null);
	const events = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/audit_events", { params: { query: { limit: 200 } } })
			),
		queryKey: ["audit", env.id],
	});
	return (
		<QueryState
			empty={{
				description: "Changes appear here.",
				title: "No audit events",
				when: (events.data ?? []).length === 0,
			}}
			query={events}
		>
			<Card>
				<Table>
					<thead>
						<Tr>
							<Th>When</Th>
							<Th>Actor</Th>
							<Th>Action</Th>
							<Th>Target</Th>
						</Tr>
					</thead>
					<tbody>
						{events.data?.map((e) => (
							<Fragment key={e.id}>
								<Tr
									className="hover:bg-muted/40 cursor-pointer"
									onClick={() => setOpen(open === e.id ? null : e.id)}
								>
									<Td>
										<When value={e.at} />
									</Td>
									<Td className="text-xs">
										{e.actor_kind}
										<span className="text-muted-foreground">
											{" "}
											{String(e.actor_id ?? "").slice(0, 12)}
										</span>
									</Td>
									<Td className="font-mono text-xs">{e.action}</Td>
									<Td className="text-xs">
										{e.target_kind}
										<span className="text-muted-foreground font-mono">
											{" "}
											{String(e.target_id ?? "").slice(0, 8)}
										</span>
									</Td>
								</Tr>
								{open === e.id ? (
									<Tr>
										<Td colSpan={4}>
											<JsonBlock
												value={{
													detail: e.detail,
													ip: e.ip,
													request_id: e.request_id,
												}}
											/>
										</Td>
									</Tr>
								) : null}
							</Fragment>
						))}
					</tbody>
				</Table>
			</Card>
		</QueryState>
	);
}
