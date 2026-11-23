"use client";

import { cn } from "@securefabric/ui/lib/utils";
import {
	ArrowRightIcon,
	CheckIcon,
	CircleAlertIcon,
	FlaskConicalIcon,
	KeyRoundIcon,
	LinkIcon,
	Loader2Icon,
	ShieldCheckIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CodeTabs, CopyField, ProviderLogo, Tabs } from "@/components/common";
import { useEnv } from "@/components/shell/env-context";
import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog, DialogContent, Select, Switch } from "@/components/ui/overlay";
import { Badge, Field, Input } from "@/components/ui/primitives";
import { MODELS, type Provider, providerOrThrow } from "@/lib/catalog";
import { timeAgo } from "@/lib/format";
import { SANDBOX_DOMAIN } from "@/lib/records";
import {
	type ConnectSession,
	createConnection,
	createConnectSession,
	logOperation,
	updateIntegration,
} from "@/lib/store";
import type { Customer, Integration } from "@/lib/types";

type Mode = "direct" | "link";
type Step = "integration" | "customer" | "credentials" | "verify";

const STEPS: { value: Step; label: string }[] = [
	{ label: "Integration", value: "integration" },
	{ label: "Customer", value: "customer" },
	{ label: "Credentials", value: "credentials" },
	{ label: "Verify", value: "verify" },
];

const INVALID = /invalid|wrong|bad/iu;

function parseTags(text: string): Record<string, string> {
	const tags: Record<string, string> = {};
	for (const part of text.split(",")) {
		const [k, ...v] = part.split("=");
		const key = k?.trim().toLowerCase();
		if (key && v.length) {
			tags[key] = v.join("=").trim();
		}
	}
	return tags;
}

export function AddConnectionDialog({
	open,
	onOpenChange,
	initialIntegration,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	initialIntegration?: string | null;
}) {
	const { env } = useEnv();
	const [mode, setMode] = useState<Mode>("direct");
	return (
		<Dialog onOpenChange={onOpenChange} open={open}>
			<DialogContent
				className="max-w-2xl"
				description="Connect an account yourself, or send your customer a Connect link and they enter their own credentials."
				title="Add connection"
			>
				<Tabs
					className="mb-6"
					onChange={setMode}
					tabs={[
						{ label: "Connect an account", value: "direct" },
						{ label: "Send a Connect link", value: "link" },
					]}
					value={mode}
				/>
				{env.integrations.length === 0 ? (
					<div className="border-border grid justify-items-center gap-3 rounded-lg border border-dashed px-6 py-10 text-center">
						<p className="text-sm font-medium">
							No integrations enabled in {env.name}
						</p>
						<p className="text-muted-foreground max-w-sm text-sm">
							Enable one from the catalog first. Every integration supports
							sandbox connections.
						</p>
						<Link
							className={buttonVariants({ variant: "primary" })}
							href={`/${env.slug}/catalog`}
							onClick={() => onOpenChange(false)}
						>
							Browse catalog
						</Link>
					</div>
				) : null}
				{env.integrations.length > 0 && mode === "direct" ? (
					<DirectFlow
						initialIntegration={initialIntegration}
						onDone={() => onOpenChange(false)}
					/>
				) : null}
				{env.integrations.length > 0 && mode === "link" ? (
					<LinkFlow initialIntegration={initialIntegration} />
				) : null}
			</DialogContent>
		</Dialog>
	);
}

function Stepper({ step }: { step: Step }) {
	const index = STEPS.findIndex((s) => s.value === step);
	return (
		<ol className="mb-6 flex items-center gap-2 text-xs">
			{STEPS.map((s, i) => (
				<li className="flex flex-1 items-center gap-2" key={s.value}>
					<span
						className={cn(
							"text-2xs flex size-5 shrink-0 items-center justify-center rounded-full border",
							i < index &&
								"bg-primary text-primary-foreground border-transparent",
							i === index && "border-foreground text-foreground font-medium",
							i > index && "border-border text-muted-foreground"
						)}
					>
						{i < index ? <CheckIcon className="size-3" /> : i + 1}
					</span>
					<span
						className={cn(
							"hidden sm:inline",
							i === index ? "text-foreground" : "text-muted-foreground"
						)}
					>
						{s.label}
					</span>
					{i < STEPS.length - 1 ? (
						<span className="bg-border h-px flex-1" />
					) : null}
				</li>
			))}
		</ol>
	);
}

function IntegrationPicker({
	integrations,
	value,
	onChange,
}: {
	integrations: Integration[];
	value: string;
	onChange: (id: string) => void;
}) {
	return (
		<fieldset className="grid gap-2 sm:grid-cols-2">
			<legend className="sr-only">Integration</legend>
			{integrations.map((i) => {
				const p = providerOrThrow(i.provider);
				const selected = value === i.id;
				return (
					<label
						className={cn(
							"has-focus-visible:ring-ring/30 flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-left transition-colors has-focus-visible:ring-2",
							selected
								? "border-foreground bg-ds-shell"
								: "border-border hover:bg-ds-shell"
						)}
						key={i.id}
					>
						<input
							checked={selected}
							className="sr-only"
							name="integration"
							onChange={() => onChange(i.id)}
							type="radio"
							value={i.id}
						/>
						<ProviderLogo provider={p} size={32} />
						<span className="grid min-w-0 flex-1">
							<span className="truncate text-sm font-medium">{p.name}</span>
							<span className="text-2xs text-muted-foreground truncate font-mono">
								{i.id}
							</span>
						</span>
						{i.allowSandbox ? (
							<FlaskConicalIcon
								aria-label="Sandbox available"
								className="text-ds-accent size-3.5"
							/>
						) : null}
					</label>
				);
			})}
		</fieldset>
	);
}

interface VerifyStep {
	detail: string;
	label: string;
}

function verifySteps(integration: Integration, sandbox: boolean): VerifyStep[] {
	const p = providerOrThrow(integration.provider);
	const scopes = [
		...new Set(integration.models.map((m) => MODELS[m].scope)),
		...integration.writeScopes,
	];
	if (sandbox) {
		return [
			{
				detail: "Isolated tenant, no vendor credentials",
				label: "Provisioning sandbox tenant",
			},
			{
				detail: `Realistic ${p.name} data for ${SANDBOX_DOMAIN}`,
				label: "Generating records",
			},
			{
				detail:
					integration.models.map((m) => MODELS[m].name).join(", ") ||
					"Actions only",
				label: "Starting initial sync",
			},
		];
	}
	return [
		{
			detail: `Test request against the ${p.name} API`,
			label: `Validating credentials with ${p.name}`,
		},
		{
			detail: scopes.join(", ") || "No read scopes",
			label: "Checking permissions",
		},
		{
			detail: "AES-256-GCM, never returned by the API",
			label: "Encrypting and storing credentials",
		},
		{
			detail:
				integration.models.map((m) => MODELS[m].name).join(", ") ||
				"Actions only",
			label: "Starting initial sync",
		},
	];
}

interface Draft {
	creds: Record<string, string>;
	email: string;
	endUserId: string;
	orgName: string;
	sandbox: boolean;
	tags: string;
}

function CustomerStep({
	draft,
	set,
	onBack,
	onNext,
}: {
	draft: Draft;
	set: (patch: Partial<Draft>) => void;
	onBack: () => void;
	onNext: () => void;
}) {
	return (
		<div className="grid gap-5">
			<p className="text-muted-foreground text-sm">
				Who this connection belongs to. SecureFabric copies these onto the
				connection as tags, so you can find it by your own IDs.
			</p>
			<div className="grid gap-4 sm:grid-cols-2">
				<Field htmlFor="c-org" label="Organization name">
					<Input
						id="c-org"
						onChange={(e) => set({ orgName: e.target.value })}
						placeholder="Northwind Health"
						value={draft.orgName}
					/>
				</Field>
				<Field htmlFor="c-id" label="Your end user ID">
					<Input
						className="font-mono"
						id="c-id"
						onChange={(e) => set({ endUserId: e.target.value })}
						placeholder="org_8f2k1"
						value={draft.endUserId}
					/>
				</Field>
			</div>
			<Field htmlFor="c-email" label="Admin email">
				<Input
					id="c-email"
					onChange={(e) => set({ email: e.target.value })}
					placeholder="secops@customer.com"
					type="email"
					value={draft.email}
				/>
			</Field>
			<Field
				help="Comma-separated key=value pairs, up to 10. Keys are lowercased."
				htmlFor="c-tags"
				label="Tags"
			>
				<Input
					className="font-mono"
					id="c-tags"
					onChange={(e) => set({ tags: e.target.value })}
					value={draft.tags}
				/>
			</Field>
			<div className="flex justify-between">
				<Button onClick={onBack} variant="ghost">
					Back
				</Button>
				<Button
					disabled={!draft.orgName.trim()}
					onClick={onNext}
					variant="primary"
				>
					Continue
					<ArrowRightIcon />
				</Button>
			</div>
		</div>
	);
}

function withDefaults(
	provider: Provider,
	creds: Record<string, string>
): Record<string, string> {
	const filled = { ...creds };
	for (const f of provider.fields) {
		if (f.options && !filled[f.key]) {
			filled[f.key] = f.options[0]?.value ?? "";
		}
	}
	return filled;
}

function SandboxToggle({
	integration,
	provider,
	sandbox,
	onChange,
}: {
	integration: Integration;
	provider: Provider;
	sandbox: boolean;
	onChange: (sandbox: boolean) => void;
}) {
	const { env } = useEnv();
	return (
		<div
			className={cn(
				"flex items-start gap-4 rounded-lg border p-4",
				sandbox ? "border-ds-accent/40 bg-ds-accent/5" : "border-border"
			)}
		>
			<FlaskConicalIcon className="text-ds-accent mt-0.5 size-5 shrink-0" />
			<div className="grid flex-1 gap-1">
				<label className="text-sm font-medium" htmlFor="use-sandbox">
					Use sandbox credentials
				</label>
				<p className="text-muted-foreground text-sm">
					Skip the credential step. SecureFabric provisions a sandbox{" "}
					{provider.name} tenant with realistic data, and the connection behaves
					like a real one: same endpoints, syncs and webhooks.
				</p>
				{integration.allowSandbox ? null : (
					<p className="text-muted-foreground text-xs">
						Sandbox connections are off for{" "}
						<span className="font-mono">{integration.id}</span> in {env.name}.{" "}
						<button
							className="text-ds-accent underline-offset-2 hover:underline"
							onClick={() => {
								updateIntegration(env.slug, integration.id, {
									allowSandbox: true,
								});
								onChange(true);
							}}
							type="button"
						>
							Allow them
						</button>
					</p>
				)}
			</div>
			<Switch
				checked={sandbox}
				disabled={!integration.allowSandbox}
				id="use-sandbox"
				onChange={onChange}
			/>
		</div>
	);
}

function CredentialFields({
	provider,
	creds,
	onChange,
}: {
	provider: Provider;
	creds: Record<string, string>;
	onChange: (creds: Record<string, string>) => void;
}) {
	return (
		<div className="grid gap-4">
			<div className="text-muted-foreground flex items-center gap-2 text-xs">
				<KeyRoundIcon className="size-3.5" />
				{provider.name} credentials. Validated before saving; never shown again.
			</div>
			{provider.fields.map((f) => (
				<Field help={f.help} htmlFor={`f-${f.key}`} key={f.key} label={f.label}>
					{f.options ? (
						<Select
							ariaLabel={f.label}
							onChange={(v) => onChange({ ...creds, [f.key]: v })}
							options={f.options}
							value={creds[f.key] ?? f.options[0]?.value ?? ""}
						/>
					) : (
						<Input
							autoComplete="off"
							className="font-mono"
							id={`f-${f.key}`}
							onChange={(e) => onChange({ ...creds, [f.key]: e.target.value })}
							placeholder={f.placeholder}
							type={f.secret ? "password" : "text"}
							value={creds[f.key] ?? ""}
						/>
					)}
				</Field>
			))}
		</div>
	);
}

function CredentialsStep({
	integration,
	draft,
	set,
	onBack,
	onNext,
}: {
	integration: Integration;
	draft: Draft;
	set: (patch: Partial<Draft>) => void;
	onBack: () => void;
	onNext: () => void;
}) {
	const provider = providerOrThrow(integration.provider);
	const filled = withDefaults(provider, draft.creds);
	const complete =
		draft.sandbox || provider.fields.every((f) => (filled[f.key] ?? "").trim());
	return (
		<div className="grid gap-5">
			<SandboxToggle
				integration={integration}
				onChange={(sandbox) => set({ sandbox })}
				provider={provider}
				sandbox={draft.sandbox}
			/>
			{draft.sandbox ? null : (
				<CredentialFields
					creds={draft.creds}
					onChange={(creds) => set({ creds })}
					provider={provider}
				/>
			)}
			<div className="flex justify-between">
				<Button onClick={onBack} variant="ghost">
					Back
				</Button>
				<Button
					disabled={!complete}
					onClick={() => {
						set({ creds: filled });
						onNext();
					}}
					variant="primary"
				>
					{draft.sandbox ? "Create sandbox connection" : "Connect"}
					<ArrowRightIcon />
				</Button>
			</div>
		</div>
	);
}

function StepIcon({
	state,
}: {
	state: "done" | "running" | "error" | "pending";
}) {
	if (state === "done") {
		return <CheckIcon className="text-ds-success size-4" />;
	}
	if (state === "running") {
		return (
			<Loader2Icon className="text-muted-foreground size-4 animate-spin" />
		);
	}
	if (state === "error") {
		return <CircleAlertIcon className="text-destructive size-4" />;
	}
	return <span className="bg-ds-line-accent size-1.5 rounded-full" />;
}

function stepState(
	i: number,
	progress: number,
	failed: boolean,
	created: boolean
): "done" | "running" | "error" | "pending" {
	if (created || i < progress) {
		return "done";
	}
	if (i === progress) {
		return failed ? "error" : "running";
	}
	return "pending";
}

function VerifyStepView({
	integration,
	draft,
	onEdit,
	onUseSandbox,
	onDone,
}: {
	integration: Integration;
	draft: Draft;
	onEdit: () => void;
	onUseSandbox: () => void;
	onDone: () => void;
}) {
	const { env } = useEnv();
	const router = useRouter();
	const provider = providerOrThrow(integration.provider);
	const steps = verifySteps(integration, draft.sandbox);
	const [progress, setProgress] = useState(0);
	const [failed, setFailed] = useState(false);
	const [created, setCreated] = useState<string | null>(null);
	// The effect below can run twice (Strict Mode, re-renders while the request
	// is in flight); this keeps it to one connection.
	const creating = useRef<boolean>(false);

	useEffect(() => {
		if (failed || created) {
			return;
		}
		if (progress >= steps.length) {
			const customer: Customer = {
				email: draft.email || "unknown@example.com",
				endUserId: draft.endUserId || "org_unknown",
				orgName: draft.orgName || "Unnamed customer",
			};
			if (!creating.current) {
				creating.current = true;
				createConnection(env.slug, {
					credentials: draft.creds,
					customer,
					integrationId: integration.id,
					sandbox: draft.sandbox,
					tags: parseTags(draft.tags),
				})
					.then(setCreated)
					.catch(() => {
						creating.current = false;
						setFailed(true);
					});
			}
			return;
		}
		const timer = setTimeout(
			() => {
				const rejected =
					!draft.sandbox &&
					progress === 0 &&
					INVALID.test(Object.values(draft.creds).join(" "));
				if (rejected) {
					setFailed(true);
					logOperation(env.slug, null, {
						action: `connection.create_failed (${integration.id}): 401 from vendor`,
						durationMs: 1210,
						status: "failed",
						type: "auth",
					});
					return;
				}
				setProgress((p) => p + 1);
			},
			650 + Math.random() * 450
		);
		return () => clearTimeout(timer);
	}, [
		progress,
		steps.length,
		failed,
		created,
		draft,
		integration.id,
		env.slug,
	]);

	const go = (path: string): void => {
		onDone();
		router.push(`/${env.slug}${path}`);
	};

	return (
		<div className="grid gap-5">
			<ol className="grid gap-3">
				{steps.map((s, i) => {
					const state = stepState(i, progress, failed, Boolean(created));
					return (
						<li className="flex items-start gap-3" key={s.label}>
							<span className="mt-0.5 flex size-5 shrink-0 items-center justify-center">
								<StepIcon state={state} />
							</span>
							<span className="grid gap-0.5">
								<span
									className={cn(
										"text-sm",
										state === "pending" && "text-muted-foreground"
									)}
								>
									{s.label}
								</span>
								<span className="text-muted-foreground text-xs">
									{s.detail}
								</span>
							</span>
						</li>
					);
				})}
			</ol>
			{failed ? (
				<div className="border-destructive/30 bg-destructive/5 grid gap-3 rounded-lg border p-4 text-sm">
					<p className="text-destructive font-medium">
						{provider.name} rejected the credentials (401 Unauthorized)
					</p>
					<p className="text-muted-foreground">
						Nothing was saved. Check the values, and that the account has the
						permissions listed for this integration.
					</p>
					<div className="flex gap-2">
						<Button onClick={onEdit} size="sm">
							Edit credentials
						</Button>
						{integration.allowSandbox ? (
							<Button onClick={onUseSandbox} size="sm" variant="ghost">
								<FlaskConicalIcon />
								Use sandbox instead
							</Button>
						) : null}
					</div>
				</div>
			) : null}
			{created ? (
				<div className="border-border bg-ds-shell grid gap-4 rounded-lg border p-4">
					<div className="flex items-center gap-2 text-sm font-medium">
						<ShieldCheckIcon className="text-ds-success size-4" />
						Connection created. The initial sync is running.
					</div>
					<CopyField label="Connection ID" value={created} />
					<div className="flex flex-wrap justify-end gap-2">
						<Button onClick={() => go(`/playground?connection=${created}`)}>
							Try it in the API playground
						</Button>
						<Button
							onClick={() => go(`/connections/${created}`)}
							variant="primary"
						>
							View connection
						</Button>
					</div>
				</div>
			) : null}
		</div>
	);
}

function DirectFlow({
	initialIntegration,
	onDone,
}: {
	initialIntegration?: string | null;
	onDone: () => void;
}) {
	const { env } = useEnv();
	const first =
		env.integrations.find((i) => i.id === initialIntegration) ??
		env.integrations[0];
	const [step, setStep] = useState<Step>(
		initialIntegration && first ? "customer" : "integration"
	);
	const [attempt, setAttempt] = useState(0);
	const [integrationId, setIntegrationId] = useState(first?.id ?? "");
	const integration = env.integrations.find((i) => i.id === integrationId);
	const [draft, setDraft] = useState<Draft>({
		creds: {},
		email: env.isProduction ? "" : "secops@acme-test.com",
		endUserId: env.isProduction ? "" : "org_test_123",
		orgName: env.isProduction ? "" : "Acme Test Org",
		sandbox: Boolean(first?.allowSandbox),
		tags: "plan=growth",
	});
	const set = (patch: Partial<Draft>): void =>
		setDraft((d) => ({ ...d, ...patch }));

	const pick = (id: string): void => {
		setIntegrationId(id);
		set({
			creds: {},
			sandbox: Boolean(env.integrations.find((i) => i.id === id)?.allowSandbox),
		});
	};

	return (
		<div>
			<Stepper step={step} />
			{step === "integration" ? (
				<div className="grid gap-5">
					<IntegrationPicker
						integrations={env.integrations}
						onChange={pick}
						value={integrationId}
					/>
					<div className="flex justify-end">
						<Button
							disabled={!integration}
							onClick={() => setStep("customer")}
							variant="primary"
						>
							Continue
							<ArrowRightIcon />
						</Button>
					</div>
				</div>
			) : null}
			{step === "customer" ? (
				<CustomerStep
					draft={draft}
					onBack={() => setStep("integration")}
					onNext={() => setStep("credentials")}
					set={set}
				/>
			) : null}
			{step === "credentials" && integration ? (
				<CredentialsStep
					draft={draft}
					integration={integration}
					onBack={() => setStep("customer")}
					onNext={() => {
						setAttempt((a) => a + 1);
						setStep("verify");
					}}
					set={set}
				/>
			) : null}
			{step === "verify" && integration ? (
				<VerifyStepView
					draft={draft}
					integration={integration}
					key={attempt}
					onDone={onDone}
					onEdit={() => setStep("credentials")}
					onUseSandbox={() => {
						set({ sandbox: true });
						setAttempt((a) => a + 1);
					}}
				/>
			) : null}
		</div>
	);
}

function LinkFlow({
	initialIntegration,
}: {
	initialIntegration?: string | null;
}) {
	const { env } = useEnv();
	const [orgName, setOrgName] = useState("");
	const [email, setEmail] = useState("");
	const [endUserId, setEndUserId] = useState("");
	const [allowed, setAllowed] = useState<string[]>(
		initialIntegration ? [initialIntegration] : []
	);
	const [session, setSession] = useState<ConnectSession | null>(null);

	if (session) {
		const body = {
			allowed_integrations: allowed,
			end_user: {
				email,
				id: endUserId || "org_123",
				organization_name: orgName,
			},
		};
		return (
			<div className="grid gap-5">
				<div className="grid gap-2">
					<p className="text-sm font-medium">
						Share this link with {orgName || "your customer"}
					</p>
					<CopyField label="Connect link" value={session.url} />
					<p className="text-muted-foreground text-xs">
						Expires {timeAgo(session.expiresAt)}. Single use. Your customer
						picks a tool, enters credentials in SecureFabric Connect, and you
						get a <span className="font-mono">connection.create.succeeded</span>{" "}
						webhook with the connection ID.
					</p>
				</div>
				<div className="grid gap-2">
					<p className="text-sm font-medium">Or embed Connect in your app</p>
					<CodeTabs
						samples={[
							{
								code: `// Server: create a session for the signed-in customer\nconst session = await securefabric.connect.sessions.create(${JSON.stringify(
									{
										allowedIntegrations: allowed,
										endUser: {
											email,
											id: endUserId || "org_123",
											organizationName: orgName,
										},
									},
									null,
									2
								)});\n\nreturn { token: session.token };`,
								label: "Server",
							},
							{
								code: `// Browser: open SecureFabric Connect with the session token\nimport { SecureFabricConnect } from "@securefabric/connect";\n\nconst connect = new SecureFabricConnect();\n\nconnect.open({\n  sessionToken: "${session.token}",\n  onEvent: (event) => {\n    if (event.type === "connect") {\n      saveConnection(event.connectionId, event.integrationId);\n    }\n  },\n});`,
								label: "Browser",
							},
							{
								code: `curl -X POST https://api.securefabric.dev/v1/connect/sessions \\\n  -H "X-API-Key: ${env.keys.secret}" \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify(body)}'`,
								label: "cURL",
							},
						]}
					/>
				</div>
				<div className="flex justify-end">
					<Button onClick={() => setSession(null)}>Create another</Button>
				</div>
			</div>
		);
	}

	return (
		<form
			className="grid gap-5"
			onSubmit={(e) => {
				e.preventDefault();
				createConnectSession(
					env.slug,
					{ email, endUserId: endUserId || "org_123", orgName },
					allowed
				)
					.then(setSession)
					.catch(() => undefined);
			}}
		>
			<div className="grid gap-4 sm:grid-cols-2">
				<Field htmlFor="l-org" label="Organization name">
					<Input
						id="l-org"
						onChange={(e) => setOrgName(e.target.value)}
						placeholder="Northwind Health"
						required
						value={orgName}
					/>
				</Field>
				<Field htmlFor="l-id" label="Your end user ID">
					<Input
						className="font-mono"
						id="l-id"
						onChange={(e) => setEndUserId(e.target.value)}
						placeholder="org_8f2k1"
						value={endUserId}
					/>
				</Field>
			</div>
			<Field htmlFor="l-email" label="Admin email">
				<Input
					id="l-email"
					onChange={(e) => setEmail(e.target.value)}
					placeholder="secops@customer.com"
					type="email"
					value={email}
				/>
			</Field>
			<fieldset className="grid gap-2">
				<legend className="mb-2 text-sm font-medium">
					Allowed integrations
				</legend>
				<p className="text-muted-foreground -mt-1 mb-1 text-xs">
					Leave all unchecked to let the customer choose from every enabled
					integration.
				</p>
				<div className="grid gap-2 sm:grid-cols-2">
					{env.integrations.map((i) => (
						<label
							className="border-border hover:bg-ds-shell flex cursor-pointer items-center gap-2.5 rounded-md border px-3 py-2 text-sm"
							key={i.id}
						>
							<input
								checked={allowed.includes(i.id)}
								className="accent-primary"
								onChange={() =>
									setAllowed(
										allowed.includes(i.id)
											? allowed.filter((a) => a !== i.id)
											: [...allowed, i.id]
									)
								}
								type="checkbox"
							/>
							<ProviderLogo provider={i.provider} size={20} />
							<span className="truncate">
								{providerOrThrow(i.provider).name}
							</span>
							{i.allowSandbox ? (
								<Badge className="ml-auto" tone="accent">
									Sandbox
								</Badge>
							) : null}
						</label>
					))}
				</div>
			</fieldset>
			<div className="flex justify-end">
				<Button type="submit" variant="primary">
					<LinkIcon />
					Create Connect link
				</Button>
			</div>
		</form>
	);
}
