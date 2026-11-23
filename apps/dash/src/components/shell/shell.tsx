"use client";

import { unwrap } from "@securefabric/client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { Fragment, useMemo, useState } from "react";
import { errorText } from "@/components/kit";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/primitives";
import { Separator } from "@/components/ui/separator";
import {
	SidebarInset,
	SidebarProvider,
	SidebarTrigger,
} from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { API_URL, api, envClient } from "@/lib/api";
import { NAV_ITEMS, OPERATOR_ITEM, SETTINGS_ITEM } from "@/lib/nav";
import type { Environment } from "@/lib/types";
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

function useCrumbs(env: Environment): Crumb[] {
	const pathname = usePathname();
	const [, , section = "", id] = pathname.split("/");
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
		{ label: decodeURIComponent(id).slice(0, 36) },
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

function ApiOffline({ error, retry }: { error: string; retry: () => void }) {
	return (
		<Centered>
			<h1 className="text-xl font-semibold">
				Can't reach the SecureFabric API
			</h1>
			<p className="text-muted-foreground max-w-md text-sm">
				The dashboard reads everything from{" "}
				<span className="text-foreground font-mono">{API_URL}</span>. Start it
				with <span className="text-foreground font-mono">make dev</span>, then
				check <span className="text-foreground font-mono">make status</span>.
			</p>
			<p className="text-muted-foreground font-mono text-xs">{error}</p>
			<Button onClick={retry} variant="outline">
				Retry now
			</Button>
		</Centered>
	);
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
				Name your account. We create a Development and a Production environment,
				each with its own keys and vault.
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
		retry: 1,
	});
	const environments = useQuery({
		enabled: Boolean(me.data && !me.data.needs_onboarding),
		queryFn: () => unwrap(api.GET("/v1/environments")),
		queryKey: ["environments"],
	});
	return { environments, me };
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
		return (
			<ApiOffline error={errorText(me.error)} retry={() => me.refetch()} />
		);
	}
	if (me.data?.needs_onboarding) {
		return <Onboarding />;
	}
	if (!(me.data && environments.data)) {
		return environments.isError ? (
			<ApiOffline
				error={errorText(environments.error)}
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
					<div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
				</SidebarInset>
				<GlobalOverlays />
			</SidebarProvider>
		</EnvContext>
	);
}
