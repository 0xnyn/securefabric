"use client";

import { cn } from "@securefabric/ui/lib/utils";
import {
	BookOpenIcon,
	CheckIcon,
	ChevronsUpDownIcon,
	KeyboardIcon,
	LaptopIcon,
	LogOutIcon,
	MessageSquareIcon,
	MoonIcon,
	NewspaperIcon,
	PlusIcon,
	SearchIcon,
	SunIcon,
	UsersIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { PersonAvatar } from "@/components/common";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { Textarea } from "@/components/ui/primitives";
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
	SidebarRail,
	useSidebar,
} from "@/components/ui/sidebar";
import { focusOf, isActive, NAV_GROUPS, SETTINGS_ITEM } from "@/lib/nav";
import type { Environment } from "@/lib/types";
import { useCommandStore } from "./command-store";
import { FocusedNav } from "./focused-nav";
import { Logo } from "./logo";
import { ShortcutKeys } from "./shortcut-keys";

function EnvDot({ env, className }: { env: Environment; className?: string }) {
	return (
		<span
			aria-hidden="true"
			className={cn(
				"size-2 shrink-0 rounded-full",
				env.isProduction ? "bg-ds-success" : "bg-ds-accent",
				className
			)}
		/>
	);
}

/**
 * The team and environment, in one switcher.
 *
 * Environment is the thing people switch, so it is the big line; the team is
 * the small one, because a playground only ever has one. Switching keeps the
 * section you are in, so comparing Dev and Production logs is one click.
 */
function WorkspaceSwitcher() {
	const { env, workspace } = useEnv();
	const router = useRouter();
	const pathname = usePathname();
	const setCreateEnvOpen = useCommandStore((s) => s.setCreateEnvOpen);
	const rest = pathname.split("/").slice(2).join("/");
	return (
		<SidebarMenu>
			<SidebarMenuItem>
				<DropdownMenu>
					<DropdownMenuTrigger
						render={
							<SidebarMenuButton
								className="data-popup-open:bg-sidebar-accent"
								size="lg"
							/>
						}
					>
						<span className="bg-primary text-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
							<Logo className="size-4.5" />
						</span>
						<span className="grid min-w-0 flex-1 text-left leading-tight">
							<span className="flex items-center gap-1.5 truncate font-medium">
								{env.name}
								<EnvDot env={env} />
							</span>
							<span className="text-muted-foreground truncate text-xs">
								{workspace.team.name} · {workspace.team.plan}
							</span>
						</span>
						<ChevronsUpDownIcon className="text-muted-foreground ml-auto size-4" />
					</DropdownMenuTrigger>
					<DropdownMenuContent
						align="start"
						className="w-(--anchor-width) min-w-64"
						sideOffset={4}
					>
						<DropdownMenuGroup>
							<DropdownMenuLabel>Environments</DropdownMenuLabel>
							{workspace.environments.map((e) => (
								<DropdownMenuItem
									key={e.id}
									onClick={() =>
										router.push(`/${e.slug}${rest ? `/${rest}` : ""}`)
									}
								>
									<CurrentMark on={e.id === env.id} />
									<EnvDot env={e} />
									<span className="flex-1 truncate">{e.name}</span>
									<span className="text-muted-foreground font-mono text-xs">
										{e.slug}
									</span>
								</DropdownMenuItem>
							))}
						</DropdownMenuGroup>
						<DropdownMenuSeparator />
						<DropdownMenuItem onClick={() => setCreateEnvOpen(true)}>
							<CurrentMark on={false} />
							<PlusIcon />
							Create environment
						</DropdownMenuItem>
						<DropdownMenuSeparator />
						<DropdownMenuGroup>
							<DropdownMenuLabel>Team</DropdownMenuLabel>
							<DropdownMenuItem>
								<span className="bg-primary text-2xs text-primary-foreground flex size-4 items-center justify-center rounded-full font-semibold">
									{workspace.team.name[0]}
								</span>
								<span className="flex-1">{workspace.team.name}</span>
								<span className="text-muted-foreground text-xs">
									{workspace.team.plan}
								</span>
							</DropdownMenuItem>
							<DropdownMenuItem
								onClick={() =>
									toast.info("Contact sales to add another team", {
										description:
											"Each team gets its own environments and billing.",
									})
								}
							>
								<PlusIcon />
								Create team
							</DropdownMenuItem>
						</DropdownMenuGroup>
					</DropdownMenuContent>
				</DropdownMenu>
			</SidebarMenuItem>
		</SidebarMenu>
	);
}

/** Looks like a search field, opens the palette. Collapsed to icons it is a
 * plain search button with the shortcut in its tooltip. */
function SearchRow() {
	const openWith = useCommandStore((s) => s.openWith);
	return (
		<SidebarMenu>
			<SidebarMenuItem>
				<SidebarMenuButton
					className="text-muted-foreground bg-background shadow-[0_0_0_1px_var(--sidebar-border)] hover:shadow-[0_0_0_1px_var(--sidebar-border)]"
					onClick={() => openWith()}
					tooltip="Search  ⌘K"
				>
					<SearchIcon />
					<span className="flex-1">Search…</span>
					<ShortcutKeys
						className="group-data-[collapsible=icon]:hidden"
						id="palette"
					/>
				</SidebarMenuButton>
			</SidebarMenuItem>
		</SidebarMenu>
	);
}

/** The main nav: the same places in the same order on every page. */
function PrimaryNav() {
	const pathname = usePathname();
	const href = useHref();
	return (
		<>
			{NAV_GROUPS.map((group) => (
				<SidebarGroup key={group.label ?? "home"}>
					{group.label ? (
						<SidebarGroupLabel>{group.label}</SidebarGroupLabel>
					) : null}
					<SidebarGroupContent>
						<SidebarMenu>
							{group.items.map((item) => (
								<SidebarMenuItem key={item.href}>
									<SidebarMenuButton
										isActive={isActive(pathname, item.href)}
										render={<Link href={href(item.href)} />}
										tooltip={item.label}
									>
										<item.icon />
										<span>{item.label}</span>
									</SidebarMenuButton>
								</SidebarMenuItem>
							))}
						</SidebarMenu>
					</SidebarGroupContent>
				</SidebarGroup>
			))}
		</>
	);
}

/** The current item's tick, in a fixed slot at the start of the row so
 * names line up whether or not they're selected. */
function CurrentMark({ on }: { on: boolean }) {
	return (
		<span className="flex size-4 shrink-0 items-center justify-center">
			{on ? <CheckIcon className="text-foreground" /> : null}
		</span>
	);
}

const THEMES = [
	{ icon: LaptopIcon, label: "System", value: "system" },
	{ icon: SunIcon, label: "Light", value: "light" },
	{ icon: MoonIcon, label: "Dark", value: "dark" },
] as const;

function HelpNav() {
	const setHelpOpen = useCommandStore((s) => s.setHelpOpen);
	return (
		<SidebarMenu>
			<SidebarMenuItem>
				<SidebarMenuButton
					onClick={() => setHelpOpen(true)}
					size="sm"
					tooltip="Keyboard shortcuts  ?"
				>
					<KeyboardIcon />
					<span className="flex-1">Keyboard shortcuts</span>
					<ShortcutKeys
						className="group-data-[collapsible=icon]:hidden"
						id="help"
					/>
				</SidebarMenuButton>
			</SidebarMenuItem>
		</SidebarMenu>
	);
}

/** Light, dark or system as one row of three icons, not three menu rows. */
function ThemeToggle({
	theme,
	onChange,
}: {
	theme: string | undefined;
	onChange: (theme: string) => void;
}) {
	return (
		<fieldset className="bg-muted flex gap-0.5 rounded-md border-0 p-0.5">
			<legend className="sr-only">Theme</legend>
			{THEMES.map((t) => (
				<button
					aria-label={t.label}
					aria-pressed={theme === t.value}
					className={cn(
						"text-muted-foreground hover:text-foreground flex size-6 items-center justify-center rounded-sm transition-colors [&_svg]:size-3.5",
						theme === t.value && "bg-background text-foreground shadow-xs"
					)}
					key={t.value}
					onClick={() => onChange(t.value)}
					title={t.label}
					type="button"
				>
					<t.icon />
				</button>
			))}
		</fieldset>
	);
}

const FEEDBACK_KINDS = [
	{ label: "Idea", value: "idea" },
	{ label: "Problem", value: "problem" },
	{ label: "Question", value: "question" },
] as const;

type FeedbackKind = (typeof FEEDBACK_KINDS)[number]["value"];

function FeedbackDialog({
	open,
	onOpenChange,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const { workspace } = useEnv();
	const [kind, setKind] = useState<FeedbackKind>("idea");
	const [message, setMessage] = useState("");
	const close = (): void => {
		onOpenChange(false);
		setMessage("");
		setKind("idea");
	};
	const send = (): void => {
		close();
		toast.success("Feedback sent", {
			description: `Thanks. We reply to ${workspace.user.email} within a working day.`,
		});
	};
	return (
		<Dialog
			onOpenChange={(next) => (next ? onOpenChange(true) : close())}
			open={open}
		>
			<DialogContent
				description="It goes straight to the people building SecureFabric."
				footer={
					<>
						<Button onClick={close}>Cancel</Button>
						<Button disabled={!message.trim()} onClick={send} variant="primary">
							Send feedback
						</Button>
					</>
				}
				title="Send feedback"
			>
				<div className="grid gap-4">
					<fieldset className="flex gap-1.5 border-0 p-0">
						<legend className="sr-only">Kind of feedback</legend>
						{FEEDBACK_KINDS.map((k) => (
							<button
								aria-pressed={kind === k.value}
								className={cn(
									"h-8 rounded-md border px-3 text-sm transition-colors",
									kind === k.value
										? "border-foreground bg-foreground text-background"
										: "border-border text-muted-foreground hover:bg-muted"
								)}
								key={k.value}
								onClick={() => setKind(k.value)}
								type="button"
							>
								{k.label}
							</button>
						))}
					</fieldset>
					<Textarea
						aria-label="Feedback"
						autoFocus
						onChange={(e) => setMessage(e.target.value)}
						onKeyDown={(e) => {
							if (
								e.key === "Enter" &&
								(e.metaKey || e.ctrlKey) &&
								message.trim()
							) {
								send();
							}
						}}
						placeholder={
							kind === "problem"
								? "What happened, and what did you expect?"
								: "What would make SecureFabric better for you?"
						}
						rows={5}
						value={message}
					/>
				</div>
			</DialogContent>
		</Dialog>
	);
}

function UserMenu() {
	const { workspace } = useEnv();
	const href = useHref();
	const router = useRouter();
	const { theme, setTheme } = useTheme();
	const [feedbackOpen, setFeedbackOpen] = useState(false);
	return (
		<SidebarMenu>
			<SidebarMenuItem>
				<DropdownMenu>
					<DropdownMenuTrigger
						render={
							<SidebarMenuButton
								className="data-popup-open:bg-sidebar-accent"
								size="lg"
							/>
						}
					>
						<PersonAvatar seed={workspace.user.email} />
						<span className="grid min-w-0 flex-1 text-left leading-tight">
							<span className="truncate font-medium">
								{workspace.user.name}
							</span>
							<span className="text-muted-foreground truncate text-xs">
								{workspace.user.email}
							</span>
						</span>
						<ChevronsUpDownIcon className="text-muted-foreground ml-auto size-4" />
					</DropdownMenuTrigger>
					<DropdownMenuContent
						align="end"
						className="min-w-60"
						side="top"
						sideOffset={4}
					>
						<DropdownMenuItem
							onClick={() => router.push(href("/settings?tab=team"))}
						>
							<UsersIcon />
							Team members
						</DropdownMenuItem>
						<DropdownMenuSeparator />
						{/* Help lives here rather than as footer rows, which would push the
						    contextual sections below the fold on a laptop screen. */}
						<DropdownMenuItem
							render={
								<a
									href="https://securefabric.dev"
									rel="noopener"
									target="_blank"
								/>
							}
						>
							<BookOpenIcon />
							Docs
						</DropdownMenuItem>
						<DropdownMenuItem
							render={
								<a
									href="https://securefabric.dev/changelog"
									rel="noopener"
									target="_blank"
								/>
							}
						>
							<NewspaperIcon />
							Changelog
						</DropdownMenuItem>
						<DropdownMenuItem onClick={() => setFeedbackOpen(true)}>
							<MessageSquareIcon />
							Send feedback
						</DropdownMenuItem>
						<DropdownMenuSeparator />
						<div className="flex items-center justify-between gap-3 px-2 py-1.5">
							<span className="text-sm">Theme</span>
							<ThemeToggle onChange={setTheme} theme={theme} />
						</div>
						<DropdownMenuSeparator />
						<DropdownMenuItem
							onClick={() =>
								toast.info("Sessions are managed by your identity provider", {
									description: `Sign out of ${workspace.team.name} SSO to end this session.`,
								})
							}
						>
							<LogOutIcon />
							Sign out
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
				<FeedbackDialog onOpenChange={setFeedbackOpen} open={feedbackOpen} />
			</SidebarMenuItem>
		</SidebarMenu>
	);
}

/** On a phone the sidebar is a sheet; following a link should close it. */
function useCloseOnNavigate(): void {
	const pathname = usePathname();
	const { isMobile, setOpenMobile } = useSidebar();
	const previous = useRef(pathname);
	useEffect(() => {
		if (isMobile && previous.current !== pathname) {
			setOpenMobile(false);
		}
		previous.current = pathname;
	}, [pathname, isMobile, setOpenMobile]);
}

/**
 * The inset sidebar, in one of two modes.
 *
 * Most pages get the main nav and nothing else. A place with sections of its
 * own (Settings, the catalog, a connection, the API playground) takes the
 * whole sidebar over, with the way back at the top, instead of stacking a
 * second list under the first.
 */
export function AppSidebar() {
	const pathname = usePathname();
	const href = useHref();
	useCloseOnNavigate();
	const focus = focusOf(pathname);
	return (
		<Sidebar collapsible="icon" variant="inset">
			<SidebarHeader>
				<WorkspaceSwitcher />
				<SearchRow />
			</SidebarHeader>
			<SidebarContent>
				{focus ? <FocusedNav focus={focus} /> : <PrimaryNav />}
			</SidebarContent>
			<SidebarFooter>
				{focus ? null : (
					<SidebarMenu>
						<SidebarMenuItem>
							<SidebarMenuButton
								render={<Link href={href(SETTINGS_ITEM.href)} />}
								tooltip="Settings"
							>
								<SETTINGS_ITEM.icon />
								<span>Settings</span>
							</SidebarMenuButton>
						</SidebarMenuItem>
					</SidebarMenu>
				)}
				<HelpNav />
				<UserMenu />
			</SidebarFooter>
			<SidebarRail />
		</Sidebar>
	);
}
