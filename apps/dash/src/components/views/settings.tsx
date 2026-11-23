"use client";

import { unwrap } from "@securefabric/client";
import { Badge } from "@securefabric/ui/components/badge";
import { Button } from "@securefabric/ui/components/button";
import { Card, CardFooter, CardHeader } from "@securefabric/ui/components/card";
import { EmptyState } from "@securefabric/ui/components/empty-state";
import { Field, Input, Textarea } from "@securefabric/ui/components/form";
import { Select } from "@securefabric/ui/components/select";
import { cn } from "@securefabric/ui/lib/utils";
import { PersonAvatar } from "@securefabric/ui/patterns/avatar";
import { CopyButton } from "@securefabric/ui/patterns/copy";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { Section } from "@securefabric/ui/patterns/section";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MailIcon, MonitorIcon, MoonIcon, SunIcon } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
	type Branding,
	type OfferedIntegration,
	PREVIEW_SOURCE,
	type PreviewState,
} from "@/components/connect/connect-flow";
import { Gated, Guard } from "@/components/domain/access";
import { ConfirmButton } from "@/components/domain/confirm-button";
import { errorText, QueryState } from "@/components/domain/query-state";
import { When } from "@/components/domain/when";
import { useAccess, useEnv } from "@/components/shell/env-context";
import { BRAND_ACCENT } from "@/components/shell/logo";
import { ROLES, type Role, roleInfo } from "@/lib/access";
import { api } from "@/lib/api";
import { SETTINGS_SECTIONS, settingsSection } from "@/lib/nav";
import type { Connector, Member } from "@/lib/types";
import { AuditLog } from "./audit-log";

const WHITESPACE = /\s+/u;
const HEX_COLOUR = /^#[0-9a-f]{6}$/iu;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/u;

interface ConnectUi {
	accent_color: string;
	logo_url: string | null;
	name: string | null;
	theme: "system" | "light" | "dark";
}

function useSaveEnv(success: string) {
	const { client } = useEnv();
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: (body: { name?: string; settings?: Record<string, unknown> }) =>
			unwrap(client.PATCH("/v1/environments/current", { body })),
		onError: (e) =>
			toast.error("Couldn't save your changes", { description: errorText(e) }),
		onSuccess: async () => {
			toast.success(success);
			await queryClient.invalidateQueries({ queryKey: ["environments"] });
		},
	});
}

const ADMIN = { admin: true } as const;

export function SettingsView() {
	const params = useSearchParams();
	const section = settingsSection(params.get("tab"));
	const meta = SETTINGS_SECTIONS.find((s) => s.value === section);
	const title = meta?.label ?? "Settings";
	if (section === "audit") {
		return (
			<Guard requires={ADMIN} title="Audit log">
				<AuditPage />
			</Guard>
		);
	}
	return (
		<>
			<PageHeader description={meta?.description} title={title} />
			<PageBody className={section === "connect" ? "max-w-6xl" : "max-w-3xl"}>
				{section === "general" ? <General /> : null}
				{section === "connect" ? <ConnectBranding /> : null}
				{section === "team" ? <Team /> : null}
			</PageBody>
		</>
	);
}

// ---------------------------------------------------------------------------
// General

function General() {
	const { env } = useEnv();
	const access = useAccess();
	const saveName = useSaveEnv("Environment renamed");
	const saveOrigins = useSaveEnv("Redirect origins saved");
	const [name, setName] = useState(env.name);
	const savedOrigins = (
		(env.settings.allowed_redirect_origins as string[] | undefined) ?? []
	).join("\n");
	const [origins, setOrigins] = useState(savedOrigins);
	const readOnly = !access.isAdmin;
	return (
		<div className="grid gap-6">
			<Card>
				<CardHeader
					description="Shown in the environment switcher and on emails to your team."
					title="Environment name"
				/>
				<div className="p-5">
					<Input
						aria-label="Environment name"
						className="max-w-sm"
						disabled={readOnly}
						maxLength={80}
						onChange={(e) => setName(e.target.value)}
						value={name}
					/>
				</div>
				<CardFooter>
					<span>Up to 80 characters.</span>
					<Gated requires={ADMIN}>
						<Button
							disabled={
								saveName.isPending || !name.trim() || name.trim() === env.name
							}
							onClick={() => saveName.mutate({ name: name.trim() })}
							size="sm"
							variant="primary"
						>
							{saveName.isPending ? "Saving…" : "Save"}
						</Button>
					</Gated>
				</CardFooter>
			</Card>
			<Card>
				<CardHeader
					description="Sites the connect page can send customers back to. One per line."
					title="Redirect origins"
				/>
				<div className="p-5">
					<Textarea
						aria-label="Redirect origins"
						className="font-mono text-xs"
						disabled={readOnly}
						onChange={(e) => setOrigins(e.target.value)}
						placeholder="https://app.example.com"
						rows={4}
						value={origins}
					/>
				</div>
				<CardFooter>
					<span>Use https. Only localhost can use http.</span>
					<Gated requires={ADMIN}>
						<Button
							disabled={saveOrigins.isPending || origins === savedOrigins}
							onClick={() =>
								saveOrigins.mutate({
									settings: {
										allowed_redirect_origins: origins
											.split(WHITESPACE)
											.map((o) => o.trim())
											.filter(Boolean),
									},
								})
							}
							size="sm"
							variant="primary"
						>
							{saveOrigins.isPending ? "Saving…" : "Save"}
						</Button>
					</Gated>
				</CardFooter>
			</Card>
			<Card>
				<CardHeader
					description="Send this with API requests that act on this environment."
					title="Environment ID"
				/>
				<div className="flex items-center gap-2 p-5">
					<code className="bg-muted rounded-md px-2.5 py-1.5 font-mono text-xs">
						{env.id}
					</code>
					<CopyButton label="Environment ID" value={env.id} />
				</div>
				<CardFooter>
					<span>
						{env.is_production ? "Production" : "Not production"} · created{" "}
						<When value={env.created_at} />
					</span>
				</CardFooter>
			</Card>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Connect page

const SAMPLE_CONNECTORS = ["GITHUB", "TENABLE", "QUALYS"];

/** What the preview offers: this environment's integrations, or a sample. */
function usePreviewIntegrations(): OfferedIntegration[] {
	const { client, env } = useEnv();
	const access = useAccess();
	const connectors = useQuery({
		queryFn: () => unwrap(api.GET("/v1/connectors")),
		queryKey: ["connectors"],
		staleTime: 5 * 60_000,
	});
	const integrations = useQuery({
		enabled: access.can("provisioning:read"),
		queryFn: () => unwrap(client.GET("/v1/integrations")),
		queryKey: ["integrations", env.id],
	});
	const byId = new Map((connectors.data ?? []).map((c) => [c.id, c] as const));
	const offer = (
		c: Connector,
		id: string,
		name: string
	): OfferedIntegration => ({
		connector: c as unknown as OfferedIntegration["connector"],
		display_name: name,
		id,
		key: id,
	});
	const enabled = (integrations.data ?? [])
		.map((i) => {
			const c = byId.get(i.connector_id);
			return c ? offer(c, i.id, i.display_name) : null;
		})
		.filter((x): x is OfferedIntegration => x !== null);
	if (enabled.length) {
		return enabled;
	}
	const live = (connectors.data ?? []).filter(
		(c) => !c.categories.includes("sandbox")
	);
	const sample = live.length ? live : (connectors.data ?? []).slice(0, 1);
	const fallback: OfferedIntegration[] = sample.map((c) =>
		offer(c, c.id, c.name)
	);
	for (const id of SAMPLE_CONNECTORS) {
		if (!fallback.some((f) => f.connector.id === id)) {
			fallback.push({
				connector: {
					auth: { connect: "form", mode: "API_KEY" },
					id,
					name: id.charAt(0) + id.slice(1).toLowerCase(),
				},
				display_name: id.charAt(0) + id.slice(1).toLowerCase(),
				id,
				key: id,
			});
		}
	}
	return fallback.slice(0, 3);
}

const STEPS: { label: string; value: PreviewState["step"] }[] = [
	{ label: "Choose a tool", value: "pick" },
	{ label: "Connect", value: "credentials" },
	{ label: "Done", value: "done" },
];

function ConnectBranding() {
	const { env } = useEnv();
	const access = useAccess();
	const save = useSaveEnv("Connect page saved");
	const saved = (env.settings.connect_ui ?? {}) as Partial<ConnectUi>;
	const [ui, setUi] = useState<ConnectUi>({
		accent_color: saved.accent_color ?? BRAND_ACCENT,
		logo_url: saved.logo_url ?? null,
		name: saved.name ?? null,
		theme: saved.theme ?? "system",
	});
	const [step, setStep] = useState<PreviewState["step"]>("pick");
	const [previewTheme, setPreviewTheme] = useState<"light" | "dark">("light");
	const integrations = usePreviewIntegrations();
	const readOnly = !access.isAdmin;
	const validAccent = HEX_COLOUR.test(ui.accent_color);
	const validLogo = !ui.logo_url || ui.logo_url.startsWith("https://");
	const dirty =
		JSON.stringify(ui) !==
		JSON.stringify({
			accent_color: saved.accent_color ?? BRAND_ACCENT,
			logo_url: saved.logo_url ?? null,
			name: saved.name ?? null,
			theme: saved.theme ?? "system",
		});
	const branding: Branding = {
		accent_color: validAccent ? ui.accent_color : BRAND_ACCENT,
		environment: env.name,
		logo_url: validLogo ? ui.logo_url : null,
		name: ui.name,
		theme: ui.theme,
	};
	return (
		<div className="grid gap-8 lg:grid-cols-[22rem_minmax(0,1fr)] lg:items-start">
			<div className="grid gap-5">
				<Field
					help="Your product's name. Leave empty to show SecureFabric."
					htmlFor="cu-name"
					label="Name"
				>
					<Input
						disabled={readOnly}
						id="cu-name"
						maxLength={60}
						onChange={(e) => setUi({ ...ui, name: e.target.value || null })}
						placeholder="SecureFabric"
						value={ui.name ?? ""}
					/>
				</Field>
				<Field
					help={
						validLogo
							? "A square https image, at least 64×64. Leave empty to use the SecureFabric logo."
							: "Use an https:// address."
					}
					htmlFor="cu-logo"
					label="Logo URL"
				>
					<Input
						aria-invalid={!validLogo}
						disabled={readOnly}
						id="cu-logo"
						onChange={(e) => setUi({ ...ui, logo_url: e.target.value || null })}
						placeholder="https://example.com/logo.png"
						type="url"
						value={ui.logo_url ?? ""}
					/>
				</Field>
				<AccentField
					disabled={readOnly}
					onChange={(accent_color) => setUi({ ...ui, accent_color })}
					value={ui.accent_color}
				/>
				<Field
					help="“Match their device” follows each visitor's light or dark setting."
					label="Appearance"
				>
					<Select
						onChange={(v) => setUi({ ...ui, theme: v })}
						options={[
							{ label: "Match their device", value: "system" },
							{ label: "Always light", value: "light" },
							{ label: "Always dark", value: "dark" },
						]}
						value={ui.theme}
					/>
				</Field>
				<div className="flex items-center gap-2 border-t pt-5">
					<Gated requires={ADMIN}>
						<Button
							disabled={save.isPending || !dirty || !validAccent || !validLogo}
							onClick={() => save.mutate({ settings: { connect_ui: ui } })}
							variant="primary"
						>
							{save.isPending ? "Saving…" : "Save changes"}
						</Button>
					</Gated>
					{dirty ? (
						<span className="text-muted-foreground text-xs">
							Unsaved changes
						</span>
					) : null}
				</div>
			</div>
			<div className="grid gap-3">
				<PreviewControls
					onPreviewTheme={setPreviewTheme}
					onStep={setStep}
					previewTheme={previewTheme}
					step={step}
					theme={ui.theme}
				/>
				<PreviewFrame
					state={{
						branding,
						forceTheme: ui.theme === "system" ? previewTheme : undefined,
						integrations,
						step,
					}}
				/>
				<p className="text-muted-foreground text-xs">
					The live connect page with sample data. Customers see it when they
					connect a tool.
				</p>
			</div>
		</div>
	);
}

function AccentField({
	value,
	onChange,
	disabled,
}: {
	value: string;
	onChange: (value: string) => void;
	disabled: boolean;
}) {
	const valid = HEX_COLOUR.test(value);
	return (
		<Field
			help={
				valid
					? "Used for the main button and progress indicators."
					: "Use a 6-digit hex color, like #533AFD."
			}
			htmlFor="cu-accent"
			label="Accent color"
		>
			<div className="flex gap-2">
				<label
					className="border-input relative size-9 shrink-0 cursor-pointer overflow-hidden rounded-md border"
					style={{ background: valid ? value : undefined }}
				>
					<span className="sr-only">Pick a color</span>
					<input
						className="absolute inset-0 cursor-pointer opacity-0"
						disabled={disabled}
						onChange={(e) => onChange(e.target.value)}
						type="color"
						value={valid ? value : BRAND_ACCENT}
					/>
				</label>
				<Input
					aria-invalid={!valid}
					className="w-32 font-mono uppercase"
					disabled={disabled}
					id="cu-accent"
					maxLength={7}
					onChange={(e) => onChange(e.target.value)}
					value={value}
				/>
				{value.toUpperCase() === BRAND_ACCENT ? null : (
					<Button
						disabled={disabled}
						onClick={() => onChange(BRAND_ACCENT)}
						variant="ghost"
					>
						Reset
					</Button>
				)}
			</div>
		</Field>
	);
}

const SEGMENT =
	"text-muted-foreground hover:text-foreground rounded-sm transition-colors";
const SEGMENT_ON = "bg-background text-foreground shadow-xs";

function PreviewControls({
	step,
	onStep,
	theme,
	previewTheme,
	onPreviewTheme,
}: {
	step: PreviewState["step"];
	onStep: (step: PreviewState["step"]) => void;
	theme: ConnectUi["theme"];
	previewTheme: "light" | "dark";
	onPreviewTheme: (theme: "light" | "dark") => void;
}) {
	return (
		<div className="flex flex-wrap items-center justify-between gap-2">
			<fieldset className="bg-muted inline-flex h-9 gap-0.5 rounded-md border-0 p-0.5">
				<legend className="sr-only">Preview step</legend>
				{STEPS.map((s) => (
					<button
						aria-pressed={step === s.value}
						className={cn(
							SEGMENT,
							"px-3 text-sm",
							step === s.value && SEGMENT_ON
						)}
						key={s.value}
						onClick={() => onStep(s.value)}
						type="button"
					>
						{s.label}
					</button>
				))}
			</fieldset>
			{theme === "system" ? (
				<fieldset className="bg-muted inline-flex h-9 gap-0.5 rounded-md border-0 p-0.5">
					<legend className="sr-only">Preview appearance</legend>
					{(
						[
							["light", SunIcon, "Light"],
							["dark", MoonIcon, "Dark"],
						] as const
					).map(([value, Icon, label]) => (
						<button
							aria-label={`Preview in ${label.toLowerCase()} mode`}
							aria-pressed={previewTheme === value}
							className={cn(
								SEGMENT,
								"flex w-9 items-center justify-center",
								previewTheme === value && SEGMENT_ON
							)}
							key={value}
							onClick={() => onPreviewTheme(value)}
							type="button"
						>
							<Icon className="size-4" />
						</button>
					))}
				</fieldset>
			) : (
				<span className="text-muted-foreground inline-flex items-center gap-1.5 text-xs">
					<MonitorIcon className="size-3.5" />
					{theme === "dark" ? "Always dark" : "Always light"}
				</span>
			)}
		</div>
	);
}

/** The connect page in a frame (its own document, so its theme is real). */
function PreviewFrame({ state }: { state: PreviewState }) {
	const frame = useRef<HTMLIFrameElement>(null);
	const latest = useRef(state);
	latest.current = state;
	const send = () =>
		frame.current?.contentWindow?.postMessage(
			{ source: PREVIEW_SOURCE, state: latest.current },
			window.location.origin
		);
	useEffect(() => {
		const onMessage = (event: MessageEvent) => {
			if (
				event.origin === window.location.origin &&
				(event.data as { source?: string; type?: string } | null)?.source ===
					PREVIEW_SOURCE &&
				(event.data as { type?: string }).type === "ready"
			) {
				send();
			}
		};
		window.addEventListener("message", onMessage);
		return () => window.removeEventListener("message", onMessage);
	});
	useEffect(() => {
		send();
	});
	return (
		<div className="border-border bg-muted/40 overflow-hidden rounded-xl border shadow-sm">
			<div className="border-border bg-background flex items-center gap-2 border-b px-3 py-2">
				<span aria-hidden="true" className="flex gap-1.5">
					<span className="bg-muted-foreground/30 size-2.5 rounded-full" />
					<span className="bg-muted-foreground/30 size-2.5 rounded-full" />
					<span className="bg-muted-foreground/30 size-2.5 rounded-full" />
				</span>
				<span className="bg-muted text-muted-foreground mx-auto truncate rounded-md px-3 py-0.5 font-mono text-xs">
					connect.securefabric.dev
				</span>
			</div>
			{/* biome-ignore lint/security/useIframeSandbox: our own same-origin page; a sandbox that allows scripts and same-origin protects nothing and browsers warn about it */}
			<iframe
				className="block h-[640px] w-full"
				ref={frame}
				src="/connect/preview"
				title="Connect page preview"
			/>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Team

/** Members and the audit log belong to signed-in people, not API keys. */
function SessionOnly({ what }: { what: string }) {
	return (
		<EmptyState
			description={`You're using a development API key (SF_DEV_API_KEY). Sign in with your account to see ${what}.`}
			title="Sign in to see this"
		/>
	);
}

function Team() {
	const { devMode } = useEnv();
	if (devMode) {
		return <SessionOnly what="your team" />;
	}
	return <TeamMembers />;
}

function TeamMembers() {
	const { me } = useEnv();
	const access = useAccess();
	const queryClient = useQueryClient();
	const members = useQuery({
		queryFn: () => unwrap(api.GET("/v1/members")),
		queryKey: ["members"],
	});
	const [email, setEmail] = useState("");
	const [role, setRole] = useState<Role>("developer");
	const validEmail = EMAIL.test(email);
	const invite = useMutation({
		mutationFn: () =>
			unwrap(api.POST("/v1/members", { body: { email, role } })),
		onError: (e) =>
			toast.error(`Couldn't invite ${email}`, { description: errorText(e) }),
		onSuccess: async (i) => {
			toast.success(`Invitation sent to ${i.email}`);
			setEmail("");
			await queryClient.invalidateQueries({ queryKey: ["members"] });
		},
	});
	const changeRole = useMutation({
		mutationFn: (v: { id: string; role: Role }) =>
			unwrap(
				api.PATCH("/v1/members/{user_id}", {
					body: { role: v.role },
					params: { path: { user_id: v.id } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't change the role", { description: errorText(e) }),
		onSuccess: async (m) => {
			toast.success(
				`${m.name ?? m.email} is now ${roleInfo(m.role)?.label ?? m.role}`
			);
			await queryClient.invalidateQueries({ queryKey: ["members"] });
		},
	});
	const remove = useMutation({
		mutationFn: (m: Member) =>
			unwrap(
				api.DELETE("/v1/members/{user_id}", {
					params: { path: { user_id: m.user_id } },
				})
			),
		onError: (e, m) =>
			toast.error(`Couldn't remove ${m.name ?? m.email}`, {
				description: errorText(e),
			}),
		onSuccess: async (_, m) => {
			toast.success(`Removed ${m.name ?? m.email}`);
			await queryClient.invalidateQueries({ queryKey: ["members"] });
		},
	});
	const admins = (members.data ?? []).filter((m) => m.role === "admin").length;
	const roleOptions = ROLES.map((r) => ({ label: r.label, value: r.value }));
	return (
		<div className="grid gap-8">
			<Gated hide requires={ADMIN}>
				<Card>
					<CardHeader
						description="They'll get an email invite. Members can use every environment in this account."
						title="Invite a teammate"
					/>
					<form
						className="flex flex-col gap-2 p-5 sm:flex-row"
						onSubmit={(e) => {
							e.preventDefault();
							if (validEmail) {
								invite.mutate();
							}
						}}
					>
						<div className="relative flex-1">
							<MailIcon className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
							<Input
								aria-label="Email address"
								className="pl-9"
								onChange={(e) => setEmail(e.target.value)}
								placeholder="name@company.com"
								type="email"
								value={email}
							/>
						</div>
						<Select
							ariaLabel="Role"
							className="sm:w-36"
							onChange={setRole}
							options={roleOptions}
							value={role}
						/>
						<Button
							disabled={!validEmail || invite.isPending}
							type="submit"
							variant="primary"
						>
							{invite.isPending ? "Sending…" : "Send invite"}
						</Button>
					</form>
					<CardFooter className="block">
						{roleInfo(role)?.description}
					</CardFooter>
				</Card>
			</Gated>
			<Section
				description={
					access.isAdmin
						? "Change a role to change what someone can see and do."
						: `You're ${access.role ? `a${access.role.value === "admin" ? "n" : ""} ${access.role.label}` : "a member"}. Only admins can invite people or change roles.`
				}
				title="Members"
			>
				<QueryState
					empty={{
						description: "Invite a teammate to get started.",
						title: "No one's here yet",
						when: (members.data ?? []).length === 0,
					}}
					query={members}
				>
					<Card className="divide-y">
						{members.data?.map((m) => {
							const self = m.user_id === me.actor_id;
							const lastAdmin = m.role === "admin" && admins <= 1;
							return (
								<div
									className="flex flex-wrap items-center gap-3 px-5 py-3.5"
									key={m.user_id}
								>
									<PersonAvatar seed={m.email} size={36} />
									<div className="grid min-w-0 flex-1">
										<span className="flex items-center gap-2 truncate font-medium">
											{m.name ?? m.email}
											{self ? <Badge>You</Badge> : null}
										</span>
										<span className="text-muted-foreground truncate text-xs">
											{m.name ? `${m.email} · ` : ""}joined{" "}
											<When value={m.joined_at} />
										</span>
									</div>
									{access.isAdmin && !self && !lastAdmin ? (
										<>
											<Select
												ariaLabel={`Role for ${m.name ?? m.email}`}
												className="w-32"
												onChange={(r) =>
													changeRole.mutate({ id: m.user_id, role: r })
												}
												options={roleOptions}
												size="sm"
												value={m.role as Role}
											/>
											<ConfirmButton
												confirmLabel="Remove"
												description={`${m.name ?? m.email} loses access to every environment right away. You can invite them again later.`}
												onConfirm={() => remove.mutate(m)}
												title={`Remove ${m.name ?? m.email}?`}
												variant="ghost"
											>
												Remove
											</ConfirmButton>
										</>
									) : (
										<span className="text-muted-foreground text-sm">
											{roleInfo(m.role)?.label ?? m.role}
										</span>
									)}
								</div>
							);
						})}
					</Card>
				</QueryState>
			</Section>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Audit log

function AuditPage() {
	const { devMode, env } = useEnv();
	if (devMode) {
		return (
			<>
				<PageHeader title="Audit log" />
				<PageBody>
					<SessionOnly what="the audit log" />
				</PageBody>
			</>
		);
	}
	return (
		<div className="flex h-full flex-col">
			<div className="border-border border-b px-4 py-4 sm:px-6">
				<h1 className="text-base font-semibold">Audit log</h1>
				<p className="text-muted-foreground text-xs">
					Who changed what in {env.name}, and when.
				</p>
			</div>
			<div className="min-h-0 flex-1">
				<AuditLog />
			</div>
		</div>
	);
}
