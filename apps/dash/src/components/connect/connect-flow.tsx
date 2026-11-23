"use client";

import {
	ClientResponseError,
	createClient,
	unwrap,
} from "@securefabric/client";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
	CheckCircle2Icon,
	ExternalLinkIcon,
	LoaderCircleIcon,
	ShieldCheckIcon,
	XCircleIcon,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
	compactValues,
	defaultsFor,
	type FormValues,
	type JsonSchema,
	SchemaForm,
	validate,
} from "@/components/schema-form";
import { Button } from "@/components/ui/button";
import { isConnectMessage, notifyParent, parentOrigin } from "./protocol";

/*
 * The hosted connect UI (part 8, section 5; CON-08). It renders entirely from
 * the session and each connector's manifest: the permission guide, the
 * credential form (JSON Schema), and the redirect step. No connector-specific
 * code. Calls go through /connect/api, which attaches the session cookie.
 */

const connectApi = createClient(
	typeof window === "undefined"
		? "http://localhost/connect/api"
		: `${window.location.origin}/connect/api`
);

interface Permission {
	access?: string;
	actions?: string[];
	description?: string | null;
	name: string;
	optional?: boolean;
	streams?: string[];
}

interface PublicConnector {
	auth: { mode: string; connect: string };
	credentials_schema?: JsonSchema;
	description?: string;
	docs_url?: string | null;
	id: string;
	logo_url?: string | null;
	name: string;
	options_schema?: JsonSchema;
	permissions?: Permission[];
}

interface OfferedIntegration {
	connector: PublicConnector;
	display_name: string;
	id: string;
	key: string;
}

interface Branding {
	accent_color?: string | null;
	environment?: string | null;
	logo_url?: string | null;
	name?: string | null;
	theme?: "system" | "light" | "dark";
}

type Outcome =
	| { kind: "verifying"; connectionId: string }
	| { kind: "success"; connectionId: string; missing: string[] }
	| { kind: "failed"; connectionId?: string; message: string };

const POLL_MS = 2000;
const POLL_LIMIT_MS = 120_000;

function sessionError(error: unknown): { title: string; detail: string } {
	if (error instanceof ClientResponseError) {
		if (error.status === 410) {
			return {
				detail: "Ask whoever sent it for a new link. Links last 30 minutes.",
				title: "This link has expired",
			};
		}
		if (error.status === 401) {
			return {
				detail:
					"Open the link you were sent again, in this browser. If it keeps happening, ask for a new link.",
				title: "This link isn't valid",
			};
		}
		return { detail: error.message, title: "Something went wrong" };
	}
	return { detail: String(error), title: "Something went wrong" };
}

function Shell({
	branding,
	children,
}: {
	branding?: Branding;
	children: React.ReactNode;
}) {
	const accent = branding?.accent_color ?? "#4f46e5";
	useEffect(() => {
		const root = document.documentElement;
		const had = root.classList.contains("dark");
		if (branding?.theme === "dark") {
			root.classList.add("dark");
		} else if (branding?.theme === "light") {
			root.classList.remove("dark");
		}
		return () => {
			root.classList.toggle("dark", had);
		};
	}, [branding?.theme]);
	return (
		<div
			className="bg-background flex min-h-svh items-start justify-center px-4 py-10 sm:items-center"
			style={{ "--connect-accent": accent } as React.CSSProperties}
		>
			<main className="border-border bg-card w-full max-w-md rounded-xl border p-6 shadow-sm">
				{branding ? (
					<header className="mb-6 flex items-center gap-2">
						{branding.logo_url ? (
							// biome-ignore lint/performance/noImgElement: customer-provided URL
							<img
								alt=""
								className="size-6 rounded"
								height={24}
								src={branding.logo_url}
								width={24}
							/>
						) : null}
						<span className="font-semibold">
							{branding.name ?? branding.environment ?? "Connect"}
						</span>
					</header>
				) : null}
				{children}
				<footer className="text-muted-foreground mt-8 flex items-center gap-1.5 text-xs">
					<ShieldCheckIcon className="size-3.5" /> Credentials are encrypted
					before they're stored and never shown again.
				</footer>
			</main>
		</div>
	);
}

function AccentButton(props: React.ComponentProps<typeof Button>) {
	return (
		<Button
			{...props}
			className="text-white"
			style={{ background: "var(--connect-accent)" }}
		/>
	);
}

function Result({
	icon,
	title,
	children,
}: {
	icon: React.ReactNode;
	title: string;
	children?: React.ReactNode;
}) {
	return (
		<div className="grid justify-items-center gap-3 py-6 text-center">
			{icon}
			<h1 className="text-lg font-semibold">{title}</h1>
			{children}
		</div>
	);
}

export function PermissionGuide({
	permissions,
}: {
	permissions: Permission[];
}) {
	if (permissions.length === 0) {
		return null;
	}
	return (
		<div className="bg-muted/40 grid gap-2 rounded-lg p-3">
			<span className="text-xs font-medium">Access this connection needs</span>
			<ul className="grid gap-1.5 text-sm">
				{permissions.map((p) => (
					<li
						className="flex items-start gap-2"
						key={`${p.name}:${p.access ?? ""}`}
					>
						<CheckCircle2Icon className="text-muted-foreground mt-0.5 size-4 shrink-0" />
						<span>
							<span className="font-medium">{p.name}</span>
							{p.access &&
							!p.name.toLowerCase().includes(p.access.toLowerCase()) ? (
								<span className="text-muted-foreground"> · {p.access}</span>
							) : null}
							{p.optional ? (
								<span className="text-muted-foreground"> (optional)</span>
							) : null}
							{p.description ? (
								<span className="text-muted-foreground block text-xs">
									{p.description}
								</span>
							) : null}
						</span>
					</li>
				))}
			</ul>
		</div>
	);
}

function usePollStatus(
	outcome: Outcome | null,
	setOutcome: (o: Outcome) => void,
	origin: string | null
) {
	const started = useRef(0);
	const connectionId =
		outcome?.kind === "verifying" ? outcome.connectionId : null;
	useEffect(() => {
		if (!connectionId) {
			return;
		}
		started.current = Date.now();
		let stop = false;
		const tick = async () => {
			if (stop) {
				return;
			}
			try {
				const s = await unwrap(
					connectApi.GET("/v1/connect/connections/{connection_id}", {
						params: { path: { connection_id: connectionId } },
					})
				);
				if (s.state === "ACTIVE") {
					setOutcome({
						connectionId,
						kind: "success",
						missing: s.missing_permissions,
					});
					notifyParent(
						{ connectionId, status: "active", type: "success" },
						origin
					);
					return;
				}
				if (s.pending_detail || s.state === "DELETED") {
					const message = s.pending_detail ?? "The connection was removed.";
					setOutcome({ connectionId, kind: "failed", message });
					notifyParent(
						{ code: s.health_code, connectionId, message, type: "error" },
						origin
					);
					return;
				}
			} catch {
				// transient; keep polling until the limit
			}
			if (Date.now() - started.current > POLL_LIMIT_MS) {
				setOutcome({
					connectionId,
					kind: "failed",
					message:
						"Verification is taking longer than expected. You can close this window; we'll keep trying.",
				});
				return;
			}
			setTimeout(tick, POLL_MS);
		};
		tick();
		return () => {
			stop = true;
		};
	}, [connectionId, origin, setOutcome]);
}

function IntegrationPicker({
	integrations,
	orgName,
	onPick,
}: {
	integrations: OfferedIntegration[];
	orgName?: string;
	onPick: (i: OfferedIntegration) => void;
}) {
	return (
		<div className="grid gap-4">
			<div className="grid gap-1">
				<h1 className="text-lg font-semibold">Connect a tool</h1>
				{orgName ? (
					<p className="text-muted-foreground text-sm">for {orgName}</p>
				) : null}
			</div>
			<ul className="grid gap-2">
				{integrations.map((i) => (
					<li key={i.id}>
						<button
							className="border-border hover:bg-muted/50 flex w-full items-center gap-3 rounded-lg border p-3 text-left"
							onClick={() => onPick(i)}
							type="button"
						>
							{i.connector.logo_url ? (
								// biome-ignore lint/performance/noImgElement: manifest-provided URL
								<img
									alt=""
									className="size-7 rounded"
									height={28}
									src={i.connector.logo_url}
									width={28}
								/>
							) : (
								<span className="bg-muted flex size-7 items-center justify-center rounded text-xs font-semibold">
									{i.display_name.slice(0, 2)}
								</span>
							)}
							<span className="grid">
								<span className="font-medium">{i.display_name}</span>
								{i.connector.description ? (
									<span className="text-muted-foreground line-clamp-1 text-xs">
										{i.connector.description}
									</span>
								) : null}
							</span>
						</button>
					</li>
				))}
			</ul>
			{integrations.length === 0 ? (
				<p className="text-muted-foreground text-sm">
					No tools are available for this link.
				</p>
			) : null}
		</div>
	);
}

/** A submit error that isn't already shown beside a field. */
function SubmitError({ error }: { error: Error | null }) {
	if (!error || (error instanceof ClientResponseError && error.errors.length)) {
		return null;
	}
	return (
		<p className="text-destructive text-sm" role="alert">
			{error.message}
		</p>
	);
}

/** Screens before the form: a bad link, loading, an expired or used link. */
function Gate({
	linkError,
	session,
}: {
	linkError: string | null;
	session: { isError: boolean; isPending: boolean; error: unknown };
}) {
	if (linkError || session.isError) {
		const { title, detail } = linkError
			? {
					detail: "Open the full link you were sent.",
					title: "This link isn't valid",
				}
			: sessionError(session.error);
		return (
			<Shell>
				<Result
					icon={<XCircleIcon className="text-destructive size-10" />}
					title={title}
				>
					<p className="text-muted-foreground text-sm">{detail}</p>
				</Result>
			</Shell>
		);
	}
	return (
		<Shell>
			<Result
				icon={
					<LoaderCircleIcon className="text-muted-foreground size-8 animate-spin" />
				}
				title="Loading…"
			/>
		</Shell>
	);
}

function CredentialStep({
	integration,
	connector,
	orgName,
	reauthorize,
	creds,
	errors,
	error,
	pending,
	onChange,
	onSubmit,
	onBack,
}: {
	integration: OfferedIntegration;
	connector: PublicConnector;
	orgName?: string;
	reauthorize: boolean;
	creds: FormValues;
	errors: Record<string, string>;
	error: Error | null;
	pending: boolean;
	onChange: (v: FormValues) => void;
	onSubmit: () => void;
	onBack: (() => void) | null;
}) {
	const redirect = connector.auth.connect === "redirect";
	return (
		<div className="grid gap-5">
			<div className="grid gap-1">
				{onBack ? (
					<button
						className="text-muted-foreground w-fit text-xs hover:underline"
						onClick={onBack}
						type="button"
					>
						← All tools
					</button>
				) : null}
				<h1 className="text-lg font-semibold">
					{reauthorize ? "Reconnect" : "Connect"} {integration.display_name}
				</h1>
				{orgName ? (
					<p className="text-muted-foreground text-sm">for {orgName}</p>
				) : null}
			</div>
			<PermissionGuide permissions={connector.permissions ?? []} />
			{redirect ? (
				<p className="text-muted-foreground text-sm">
					You'll continue at {connector.name} to approve access, then come back
					here.
				</p>
			) : (
				<SchemaForm
					errors={errors}
					idPrefix="connect"
					onChange={onChange}
					schema={connector.credentials_schema}
					values={creds}
				/>
			)}
			<SubmitError error={error} />
			<AccentButton disabled={pending} onClick={onSubmit} size="lg">
				{pending ? <LoaderCircleIcon className="animate-spin" /> : null}
				{redirect ? `Continue to ${connector.name}` : "Connect"}
				{redirect ? <ExternalLinkIcon /> : null}
			</AccentButton>
			{connector.docs_url ? (
				<a
					className="text-muted-foreground text-xs hover:underline"
					href={connector.docs_url}
					rel="noreferrer"
					target="_blank"
				>
					Where do I find these?
				</a>
			) : null}
		</div>
	);
}

export function ConnectFlow() {
	const params = useSearchParams();
	const origin = parentOrigin(params.get("origin"));
	const linkError = params.get("error");
	const session = useQuery({
		enabled: !linkError,
		queryFn: () => unwrap(connectApi.GET("/v1/connect/session")),
		queryKey: ["connect-session"],
		retry: false,
	});
	const [picked, setPicked] = useState<string | null>(null);
	const [creds, setCreds] = useState<FormValues>({});
	const [errors, setErrors] = useState<Record<string, string>>({});
	const [outcome, setOutcome] = useState<Outcome | null>(null);
	const popup = useRef<Window | null>(null);
	usePollStatus(outcome, setOutcome, origin);

	useEffect(() => {
		notifyParent({ type: "ready" }, origin);
	}, [origin]);

	// The redirect popup reports back from /connect/done (same origin).
	useEffect(() => {
		const onMessage = (event: MessageEvent) => {
			if (
				event.origin !== window.location.origin ||
				!isConnectMessage(event.data)
			) {
				return;
			}
			if (event.data.type === "redirect_complete") {
				const { connectionId, status } = event.data;
				if (status === "error" || status === "failed") {
					setOutcome({
						connectionId,
						kind: "failed",
						message: "The vendor didn't grant access.",
					});
				} else {
					setOutcome({ connectionId, kind: "verifying" });
				}
			}
		};
		window.addEventListener("message", onMessage);
		return () => window.removeEventListener("message", onMessage);
	}, []);

	const integrations = (session.data?.integrations ??
		[]) as unknown as OfferedIntegration[];
	const branding = session.data?.branding as Branding | undefined;
	const chosen =
		integrations.find((i) => i.id === picked) ??
		(integrations.length === 1 ? integrations[0] : undefined);
	const connector = chosen?.connector;
	const redirect = connector?.auth.connect === "redirect";

	const create = useMutation({
		mutationFn: () =>
			unwrap(
				connectApi.POST("/v1/connect/connections", {
					body: {
						credentials: redirect ? null : compactValues(creds),
						integration: chosen?.id ?? "",
						mode: "install",
						options:
							(session.data?.option_presets as
								| Record<string, unknown>
								| undefined) ?? {},
					},
					headers: { "Idempotency-Key": crypto.randomUUID() },
				})
			),
		onError: (e) => {
			if (e instanceof ClientResponseError && e.errors.length) {
				setErrors(
					Object.fromEntries(
						e.errors.map((f) => [
							f.field.replace("credentials.", ""),
							f.message,
						])
					)
				);
			}
			popup.current?.close();
		},
		onSuccess: (r) => {
			if (r.authorize_url) {
				if (popup.current && !popup.current.closed) {
					popup.current.location.href = r.authorize_url;
				} else {
					window.location.assign(r.authorize_url);
				}
				setOutcome({ connectionId: r.id, kind: "verifying" });
				return;
			}
			setOutcome({ connectionId: r.id, kind: "verifying" });
		},
	});

	const submit = () => {
		if (!chosen) {
			return;
		}
		if (redirect) {
			// Open synchronously, inside the click, so popup blockers allow it.
			popup.current = window.open(
				"about:blank",
				"securefabric-connect",
				"popup,width=720,height=800"
			);
			create.mutate();
			return;
		}
		const errs = validate(connector?.credentials_schema, creds);
		setErrors(errs);
		if (Object.keys(errs).length === 0) {
			create.mutate();
		}
	};

	if (linkError || !session.isSuccess) {
		return <Gate linkError={linkError} session={session} />;
	}
	const s = session.data;
	if (s.used_at && !outcome) {
		return (
			<Shell branding={branding}>
				<Result
					icon={<XCircleIcon className="text-muted-foreground size-10" />}
					title="This link was already used"
				>
					<p className="text-muted-foreground text-sm">
						Each link connects one account. Ask for a new link to connect
						another.
					</p>
				</Result>
			</Shell>
		);
	}
	if (outcome) {
		return (
			<Shell branding={branding}>
				<OutcomeView
					missing={outcome.kind === "success" ? outcome.missing : []}
					outcome={outcome}
					redirectSuccess={s.redirect_success}
				/>
			</Shell>
		);
	}
	const org = s.organization as { name?: string } | null;
	return (
		<Shell branding={branding}>
			{chosen && connector ? (
				<CredentialStep
					connector={connector}
					creds={creds}
					error={create.error}
					errors={errors}
					integration={chosen}
					onBack={integrations.length > 1 ? () => setPicked(null) : null}
					onChange={setCreds}
					onSubmit={submit}
					orgName={org?.name}
					pending={create.isPending}
					reauthorize={Boolean(s.reauthorize_connection_id)}
				/>
			) : (
				<IntegrationPicker
					integrations={integrations}
					onPick={(i) => {
						setPicked(i.id);
						setCreds(defaultsFor(i.connector.credentials_schema));
						setErrors({});
					}}
					orgName={org?.name}
				/>
			)}
		</Shell>
	);
}

function OutcomeView({
	outcome,
	missing,
	redirectSuccess,
}: {
	outcome: Outcome;
	missing: string[];
	redirectSuccess: string | null;
}) {
	useEffect(() => {
		if (
			outcome.kind === "success" &&
			redirectSuccess &&
			window.parent === window
		) {
			const url = new URL(redirectSuccess);
			url.searchParams.set("connection_id", outcome.connectionId);
			url.searchParams.set("status", "active");
			window.location.assign(url.toString());
		}
	}, [outcome, redirectSuccess]);
	if (outcome.kind === "verifying") {
		return (
			<Result
				icon={
					<LoaderCircleIcon
						className="size-8 animate-spin"
						style={{ color: "var(--connect-accent)" }}
					/>
				}
				title="Checking access…"
			>
				<p className="text-muted-foreground text-sm">
					We're confirming what this connection can read. This usually takes a
					few seconds.
				</p>
			</Result>
		);
	}
	if (outcome.kind === "failed") {
		return (
			<Result
				icon={<XCircleIcon className="text-destructive size-10" />}
				title="We couldn't connect"
			>
				<p className="text-muted-foreground text-sm">{outcome.message}</p>
			</Result>
		);
	}
	return (
		<Result
			icon={<CheckCircle2Icon className="size-10 text-emerald-500" />}
			title="Connected"
		>
			{missing.length ? (
				<p className="text-muted-foreground text-sm">
					Connected, but some data isn't readable yet: {missing.join(", ")}.
					Grant the missing permissions in the tool to include it.
				</p>
			) : (
				<p className="text-muted-foreground text-sm">
					You can close this window.
				</p>
			)}
		</Result>
	);
}

/**
 * `/connect/done?connection_id&status`: where the vendor sends the browser
 * back after a redirect step (GitHub App install). In the popup it reports to
 * the connect page and closes; opened directly it shows the outcome.
 */
export function ConnectDone() {
	const params = useSearchParams();
	const connectionId = params.get("connection_id") ?? "";
	const status = params.get("status") ?? "";
	const [relayed, setRelayed] = useState(false);
	const [outcome, setOutcome] = useState<Outcome | null>(null);
	useEffect(() => {
		if (window.opener && !(window.opener as Window).closed) {
			(window.opener as Window).postMessage(
				{
					connectionId,
					source: "securefabric-connect",
					status,
					type: "redirect_complete",
				},
				window.location.origin
			);
			setRelayed(true);
			window.close();
			return;
		}
		if (!connectionId || status === "error" || status === "failed") {
			setOutcome({
				connectionId: connectionId || undefined,
				kind: "failed",
				message: "The vendor didn't grant access. Try the link again.",
			});
		} else {
			setOutcome({ connectionId, kind: "verifying" });
		}
	}, [connectionId, status]);
	usePollStatus(outcome, setOutcome, null);
	return (
		<Shell>
			{relayed ? (
				<Result
					icon={<CheckCircle2Icon className="size-10 text-emerald-500" />}
					title="Done"
				>
					<p className="text-muted-foreground text-sm">
						You can close this window.
					</p>
				</Result>
			) : null}
			{outcome ? (
				<OutcomeView
					missing={outcome.kind === "success" ? outcome.missing : []}
					outcome={outcome}
					redirectSuccess={null}
				/>
			) : null}
		</Shell>
	);
}
