"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { Fragment } from "react";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import {
	SidebarInset,
	SidebarProvider,
	SidebarTrigger,
} from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { API_URL } from "@/lib/api";
import { getProvider } from "@/lib/catalog";
import { NAV_ITEMS, SETTINGS_ITEM } from "@/lib/nav";
import { refresh, useLoadState, useWorkspace } from "@/lib/store";
import type { Environment, Workspace } from "@/lib/types";
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

/** The name a detail page's id stands for, so the trail reads "Connections
 * › Acme Corp" rather than a connection ID. */
function detailLabel(env: Environment, section: string, id: string): string {
	switch (section) {
		case "connections":
			return env.connections.find((c) => c.id === id)?.customer.orgName ?? id;
		case "catalog":
			return getProvider(id)?.name ?? id;
		case "integrations": {
			const integration = env.integrations.find((i) => i.id === id);
			return integration ? (getProvider(integration.provider)?.name ?? id) : id;
		}
		default:
			return id;
	}
}

function useCrumbs(env: Environment): Crumb[] {
	const pathname = usePathname();
	const [, , section = "", id] = pathname.split("/");
	const base = `/${env.slug}`;
	const item = [...NAV_ITEMS, SETTINGS_ITEM].find(
		(n) => n.href === (section ? `/${section}` : "")
	);
	if (!item) {
		return [];
	}
	if (!id) {
		return [{ label: item.label }];
	}
	return [
		{ href: `${base}${item.href}`, label: item.label },
		{ label: detailLabel(env, section, decodeURIComponent(id)) },
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
						<Fragment key={c.label}>
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

/** Overlays that any page, the keyboard or the palette can open. */
function GlobalOverlays({ workspace }: { workspace: Workspace }) {
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
				workspace={workspace}
			/>
		</>
	);
}

function LoadingShell() {
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
				<div className="grid gap-4 pt-6 md:grid-cols-4">
					<Skeleton className="h-28" />
					<Skeleton className="h-28" />
					<Skeleton className="h-28" />
					<Skeleton className="h-28" />
				</div>
			</div>
		</div>
	);
}

/** The API can't be reached and nothing has loaded yet. */
function ApiOffline({ error }: { error: string }) {
	return (
		<div className="flex min-h-svh flex-col items-center justify-center gap-4 px-6 text-center">
			<Logo className="size-8" />
			<h1 className="text-xl font-semibold">
				Can't reach the SecureFabric API
			</h1>
			<p className="text-muted-foreground max-w-md text-sm">
				The dash reads everything from{" "}
				<span className="text-foreground font-mono">{API_URL}</span>. Start the
				stack with <span className="text-foreground font-mono">make dev</span>{" "}
				(or <span className="text-foreground font-mono">make dev-api</span>),
				then check{" "}
				<span className="text-foreground font-mono">make status</span>.
			</p>
			<p className="text-muted-foreground font-mono text-xs">{error}</p>
			<button
				className="border-border hover:bg-muted rounded-md border px-3 py-1.5 text-sm"
				onClick={() => refresh()}
				type="button"
			>
				Retry now
			</button>
		</div>
	);
}

function MissingEnv({
	slug,
	workspace,
}: {
	slug: string;
	workspace: Workspace;
}) {
	return (
		<div className="flex min-h-svh flex-col items-center justify-center gap-4 px-6 text-center">
			<Logo className="size-8" />
			<h1 className="text-xl font-semibold">
				Environment <span className="font-mono">{slug}</span> doesn't exist
			</h1>
			<p className="text-muted-foreground max-w-sm text-sm">
				It may have been deleted, or the workspace was reset.
			</p>
			<div className="flex gap-2">
				{workspace.environments.map((e) => (
					<Link
						className="border-border hover:bg-muted rounded-md border px-3 py-1.5 text-sm"
						href={`/${e.slug}`}
						key={e.id}
					>
						Go to {e.name}
					</Link>
				))}
			</div>
		</div>
	);
}

/**
 * The app frame: an inset sidebar and a content panel.
 *
 * The frame is exactly the viewport and never scrolls; the panel's `main`
 * does. That keeps the sidebar and header in place, and gives full-height
 * pages (the logs table) a definite height to fill.
 */
export function EnvShell({ children }: { children: React.ReactNode }) {
	const workspace = useWorkspace();
	const load = useLoadState();
	const params = useParams<{ env: string }>();
	if (!workspace) {
		return load.status === "offline" ? (
			<ApiOffline error={load.error} />
		) : (
			<LoadingShell />
		);
	}
	const env = workspace.environments.find((e) => e.slug === params.env);
	if (!env) {
		return <MissingEnv slug={params.env} workspace={workspace} />;
	}
	return (
		<EnvContext value={{ env, workspace }}>
			<SidebarProvider className="h-svh overflow-hidden">
				<AppSidebar />
				<SidebarInset className="min-h-0 overflow-hidden">
					<Header env={env} />
					<div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
				</SidebarInset>
				<GlobalOverlays workspace={workspace} />
			</SidebarProvider>
		</EnvContext>
	);
}
