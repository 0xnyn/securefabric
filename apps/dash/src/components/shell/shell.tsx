"use client";

import { ClientResponseError, unwrap } from "@securefabric/client";
import { Button } from "@securefabric/ui/components/button";
import { Field, Input } from "@securefabric/ui/components/form";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@securefabric/ui/primitives/breadcrumb";
import { Separator } from "@securefabric/ui/primitives/separator";
import {
	SidebarInset,
	SidebarProvider,
	SidebarTrigger,
} from "@securefabric/ui/primitives/sidebar";
import { Skeleton } from "@securefabric/ui/primitives/skeleton";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { Fragment, useMemo, useState } from "react";
import { Guard } from "@/components/domain/access";
import { errorText } from "@/components/domain/query-state";
import { API_URL, api, envClient } from "@/lib/api";
import { needsSignIn, retryUnlessAuth } from "@/lib/auth";
import { PLANNED } from "@/lib/connector-catalog";
import { NAV_ITEMS, OPERATOR_ITEM, SETTINGS_ITEM, sectionOf } from "@/lib/nav";
import type { Connector, Environment } from "@/lib/types";
import { AppSidebar } from "./app-sidebar";
import { CommandPalette } from "./command-palette";
import { useCommandStore } from "./command-store";
import { EnvContext } from "./env-context";
import { CreateEnvironmentDialog } from "./env-dialog";
import { KeyboardShortcuts } from "./keyboard-shortcuts";
import { Logo } from "./logo";
import { ShortcutsDialog } from "./shortcuts-dialog";

interface Crumb {
	href?: string;
	label: string;
}

/** A readable name for an id in the URL, when the page has one to offer. */
function useCrumbName(
	section: string,
	id: string | undefined
): string | undefined {
	const queryClient = useQueryClient();
	if (!id || section !== "catalog") {
		return;
	}
	const live = queryClient.getQueryData<Connector[]>(["connectors"]);
	return (
		live?.find((c) => c.id === id)?.name ??
		PLANNED.find((p) => p.id === id)?.name
	);
}

function useCrumbs(env: Environment): Crumb[] {
	const pathname = usePathname();
	const [, , section = "", id] = pathname.split("/");
	const name = useCrumbName(section, id);
	const base = `/${env.slug}`;
	const item = [...NAV_ITEMS, SETTINGS_ITEM, OPERATOR_ITEM].find(
		(n) => n.href === (section ? `/${section}` : "")
	);
	if (section === "jobs") {
		return [
			{ href: `${base}/connections`, label: "Connections" },
			{ label: `Job ${id?.slice(0, 8) ?? ""}` },
		];
	}
	if (!item) {
		return [];
	}
	if (!id) {
		return [{ label: item.label }];
	}
	return [
		{ href: `${base}${item.href}`, label: item.label },
		{ label: name ?? decodeURIComponent(id).slice(0, 36) },
	];
}

function Header({ env }: { env: Environment }) {
	const crumbs = useCrumbs(env);
	return (
		<header className="bg-background/90 sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2 border-b px-3 backdrop-blur md:rounded-t-xl">
			<SidebarTrigger className="-ml-1" />
			<Separator className="mr-1 data-vertical:h-4" orientation="vertical" />
			<Breadcrumb className="min-w-0">
				<BreadcrumbList className="flex-nowrap">
					<BreadcrumbItem className="hidden sm:inline-flex">
						<BreadcrumbLink render={<Link href={`/${env.slug}`} />}>
							{env.name}
						</BreadcrumbLink>
					</BreadcrumbItem>
					{crumbs.map((c, i) => (
						<Fragment key={c.href ?? c.label}>
							<BreadcrumbSeparator
								className={i === 0 ? "hidden sm:inline-flex" : undefined}
							/>
							<BreadcrumbItem className="min-w-0">
								{c.href ? (
									<BreadcrumbLink render={<Link href={c.href} />}>
										{c.label}
									</BreadcrumbLink>
								) : (
									<BreadcrumbPage className="truncate">
										{c.label}
									</BreadcrumbPage>
								)}
							</BreadcrumbItem>
						</Fragment>
					))}
				</BreadcrumbList>
			</Breadcrumb>
		</header>
	);
}

function GlobalOverlays() {
	const createEnvOpen = useCommandStore((s) => s.createEnvOpen);
	const setCreateEnvOpen = useCommandStore((s) => s.setCreateEnvOpen);
	return (
		<>
			<KeyboardShortcuts />
			<CommandPalette />
			<ShortcutsDialog />
			<CreateEnvironmentDialog
				onOpenChange={setCreateEnvOpen}
				open={createEnvOpen}
			/>
		</>
	);
}

export function LoadingShell() {
	return (
		<div className="bg-sidebar flex h-svh">
			<div className="hidden w-64 shrink-0 flex-col gap-3 p-4 md:flex">
				<div className="flex items-center gap-2">
					<Logo className="size-6" />
					<Skeleton className="h-5 w-28" />
				</div>
				<Skeleton className="h-8" />
				{NAV_ITEMS.map((n) => (
					<Skeleton className="h-6" key={n.href} />
				))}
			</div>
			<div className="bg-background m-0 grid flex-1 content-start gap-4 p-10 md:m-2 md:ml-0 md:rounded-xl">
				<Skeleton className="h-8 w-56" />
				<Skeleton className="h-4 w-96 max-w-full" />
			</div>
		</div>
	);
}

function Centered({ children }: { children: React.ReactNode }) {
	return (
		<div className="flex min-h-svh flex-col items-center justify-center gap-4 px-6 text-center">
			<Logo className="size-8" />
			{children}
		</div>
	);
}

/** The proxy's own errors when the API is down or hung (app/api/sf). */
const UNREACHABLE = new Set(["api_unreachable", "api_timeout"]);

/**
 * `/v1/me` or `/v1/environments` failed. Says which of three things went wrong:
 * the API is down, the session is gone (the query cache is already sending you
 * to sign-in), or the API rejects the session, which signing in again won't fix.
 */
function AccountError({ error, retry }: { error: unknown; retry: () => void }) {
	const detail = (
		<p className="text-muted-foreground font-mono text-xs">
			{errorText(error)}
		</p>
	);
	if (needsSignIn(error)) {
		return (
			<Centered>
				<h1 className="text-xl font-semibold">Your session ended</h1>
				<p className="text-muted-foreground max-w-md text-sm">
					Sign in again to continue.
				</p>
				{detail}
				<Button render={<a href="/logout" />} variant="primary">
					Sign in again
				</Button>
			</Centered>
		);
	}
	if (
		error instanceof ClientResponseError &&
		!UNREACHABLE.has(error.code) &&
		error.status !== 502 &&
		error.status !== 504
	) {
		return (
			<Centered>
				<h1 className="text-xl font-semibold">Couldn't load your account</h1>
				<p className="text-muted-foreground max-w-md text-sm">
					{rejectedText(error.status)}
				</p>
				{detail}
				<div className="flex gap-2">
					<Button onClick={retry} variant="outline">
						Try again
					</Button>
					<Button render={<a href="/logout" />} variant="outline">
						Sign out
					</Button>
				</div>
			</Centered>
		);
	}
	return (
		<Centered>
			<h1 className="text-xl font-semibold">Can't reach SecureFabric</h1>
			{LOCAL_DEV ? (
				<p className="text-muted-foreground max-w-md text-sm">
					The dashboard reads everything from{" "}
					<span className="text-foreground font-mono">{API_URL}</span>. Start it
					with <span className="text-foreground font-mono">make dev</span>, then
					check <span className="text-foreground font-mono">make status</span>.
				</p>
			) : (
				<p className="text-muted-foreground max-w-md text-sm">
					Check your internet connection and try again. If it keeps happening,
					share the details below with us.
				</p>
			)}
			{detail}
			<Button onClick={retry} variant="outline">
				Try again
			</Button>
		</Centered>
	);
}

/**
 * Setup hints (env vars, make targets) help whoever runs the stack locally
 * and mean nothing to a customer, so production gets plain words instead.
 */
const LOCAL_DEV = process.env.NODE_ENV === "development";

function rejectedText(status: number): string {
	if (status !== 401 && status !== 403) {
		return "Our server hit an error. Try again, or share the request ID below with us.";
	}
	return LOCAL_DEV
		? "You're signed in, but the API doesn't accept this session. Make sure WORKOS_CLIENT_ID and WORKOS_API_KEY match in the root .env (API) and apps/dash/.env.local (dashboard), then restart make dev."
		: "Your session wasn't accepted. Sign out, then sign in again.";
}

/** First sign-in with no account: name it; dev and prod are created for you. */
function Onboarding() {
	const queryClient = useQueryClient();
	const [name, setName] = useState("");
	const onboard = useMutation({
		mutationFn: () =>
			unwrap(
				api.POST("/v1/onboarding", { body: { account_name: name.trim() } })
			),
		onSuccess: () => queryClient.invalidateQueries(),
	});
	return (
		<Centered>
			<h1 className="text-xl font-semibold">Welcome to SecureFabric</h1>
			<p className="text-muted-foreground max-w-sm text-sm">
				Name your account. We'll create Development and Production environments,
				each with its own API keys.
			</p>
			<form
				className="grid w-full max-w-sm gap-3 text-left"
				onSubmit={(e) => {
					e.preventDefault();
					if (name.trim().length >= 2) {
						onboard.mutate();
					}
				}}
			>
				<Field htmlFor="account-name" label="Account name">
					<Input
						autoFocus
						id="account-name"
						onChange={(e) => setName(e.target.value)}
						value={name}
					/>
				</Field>
				{onboard.isError ? (
					<p className="text-destructive text-sm">{errorText(onboard.error)}</p>
				) : null}
				<Button
					disabled={onboard.isPending || name.trim().length < 2}
					type="submit"
					variant="primary"
				>
					Create account
				</Button>
			</form>
		</Centered>
	);
}

function MissingEnv({
	slug,
	environments,
}: {
	slug: string;
	environments: Environment[];
}) {
	return (
		<Centered>
			<h1 className="text-xl font-semibold">
				Environment <span className="font-mono">{slug}</span> doesn't exist
			</h1>
			<div className="flex flex-wrap justify-center gap-2">
				{environments.map((e) => (
					<Link
						className="border-border hover:bg-muted rounded-md border px-3 py-1.5 text-sm"
						href={`/${e.slug}`}
						key={e.id}
					>
						Go to {e.name}
					</Link>
				))}
			</div>
		</Centered>
	);
}

export function useAccount() {
	const me = useQuery({
		queryFn: () => unwrap(api.GET("/v1/me")),
		queryKey: ["me"],
		retry: (count, error) => count < 1 && retryUnlessAuth(count, error),
	});
	const environments = useQuery({
		enabled: Boolean(me.data && !me.data.needs_onboarding),
		queryFn: () => unwrap(api.GET("/v1/environments")),
		queryKey: ["environments"],
	});
	return { environments, me };
}

/** A page whose nav item needs a role or scope this person lacks says so
 * instead of rendering (the sidebar already hides its link). */
function RouteGuard({ children }: { children: React.ReactNode }) {
	const pathname = usePathname();
	const section = sectionOf(pathname);
	const item = NAV_ITEMS.find((n) => n.href === (section ? `/${section}` : ""));
	if (!item?.requires) {
		return <>{children}</>;
	}
	return (
		<Guard requires={item.requires} title={item.label}>
			{children}
		</Guard>
	);
}

/**
 * The app frame: an inset sidebar and a content panel. The frame never
 * scrolls; the panel's `main` does.
 */
export function EnvShell({ children }: { children: React.ReactNode }) {
	const { me, environments } = useAccount();
	const params = useParams<{ env: string }>();
	const env = environments.data?.find(
		(e) => e.slug === params.env || e.id === params.env
	);
	const client = useMemo(() => (env ? envClient(env.id) : null), [env]);
	if (me.isError) {
		return <AccountError error={me.error} retry={() => me.refetch()} />;
	}
	if (me.data?.needs_onboarding) {
		return <Onboarding />;
	}
	if (!(me.data && environments.data)) {
		return environments.isError ? (
			<AccountError
				error={environments.error}
				retry={() => environments.refetch()}
			/>
		) : (
			<LoadingShell />
		);
	}
	if (!(env && client)) {
		return <MissingEnv environments={environments.data} slug={params.env} />;
	}
	return (
		<EnvContext
			value={{
				client,
				devMode: me.data.kind === "api_key",
				env,
				environments: environments.data,
				me: me.data,
			}}
		>
			<SidebarProvider className="h-svh overflow-hidden">
				<AppSidebar />
				<SidebarInset className="min-h-0 overflow-hidden">
					<Header env={env} />
					<div className="min-h-0 flex-1 overflow-y-auto">
						<RouteGuard>{children}</RouteGuard>
					</div>
				</SidebarInset>
				<GlobalOverlays />
			</SidebarProvider>
		</EnvContext>
	);
}
