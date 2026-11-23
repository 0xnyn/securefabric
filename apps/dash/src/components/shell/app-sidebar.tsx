"use client";

import { Button } from "@securefabric/ui/components/button";
import { Dialog, DialogContent } from "@securefabric/ui/components/dialog";
import { Textarea } from "@securefabric/ui/components/form";
import { cn } from "@securefabric/ui/lib/utils";
import { EntityAvatar, PersonAvatar } from "@securefabric/ui/patterns/avatar";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@securefabric/ui/primitives/dropdown-menu";
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
} from "@securefabric/ui/primitives/sidebar";
import {
	ArrowUpRightIcon,
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
import { useAccess, useEnv, useHref } from "@/components/shell/env-context";
import { roleInfo } from "@/lib/access";
import {
	DOCS_URL,
	focusOf,
	isActive,
	OPERATOR_ITEM,
	SETTINGS_ITEM,
	visibleNavGroups,
} from "@/lib/nav";
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
				env.is_production ? "bg-ds-success" : "bg-ds-accent",
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
	const { env, environments, me } = useEnv();
	const router = useRouter();
	const pathname = usePathname();
	const accountName = me.account?.name ?? "SecureFabric";
	const plan = me.account?.plan ?? "free";
	const planLabel = plan.charAt(0).toUpperCase() + plan.slice(1);
	const access = useAccess();
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
								{accountName} · {planLabel}
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
							{environments.map((e) => (
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
						{access.isAdmin ? (
							<>
								<DropdownMenuSeparator />
								<DropdownMenuItem onClick={() => setCreateEnvOpen(true)}>
									<CurrentMark on={false} />
									<PlusIcon />
									Create environment
								</DropdownMenuItem>
							</>
						) : null}
						<DropdownMenuSeparator />
						<DropdownMenuGroup>
							<DropdownMenuLabel>Account</DropdownMenuLabel>
							<DropdownMenuItem>
								<EntityAvatar name={accountName} size={16} />
								<span className="flex-1">{accountName}</span>
								<span className="text-muted-foreground text-xs">
									{planLabel}
								</span>
							</DropdownMenuItem>
							<DropdownMenuItem
								onClick={() =>
									toast.info("Contact sales to add another account", {
										description:
											"Each account gets its own environments and billing.",
									})
								}
							>
								<PlusIcon />
								Add account
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
	const { me } = useEnv();
	const access = useAccess();
	return (
		<>
			{visibleNavGroups(access).map((group) => (
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
			{me.is_operator ? (
				<SidebarGroup>
					<SidebarGroupLabel>Operators</SidebarGroupLabel>
					<SidebarGroupContent>
						<SidebarMenu>
							<SidebarMenuItem>
								<SidebarMenuButton
									isActive={isActive(pathname, OPERATOR_ITEM.href)}
									render={<Link href={href(OPERATOR_ITEM.href)} />}
									tooltip={OPERATOR_ITEM.label}
								>
									<OPERATOR_ITEM.icon />
									<span>{OPERATOR_ITEM.label}</span>
								</SidebarMenuButton>
							</SidebarMenuItem>
						</SidebarMenu>
					</SidebarGroupContent>
				</SidebarGroup>
			) : null}
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
					render={<a href={DOCS_URL} rel="noopener" target="_blank" />}
					size="sm"
					tooltip="Docs and API reference"
				>
					<BookOpenIcon />
					<span className="flex-1">Docs and API reference</span>
					<ArrowUpRightIcon className="text-muted-foreground group-data-[collapsible=icon]:hidden" />
				</SidebarMenuButton>
			</SidebarMenuItem>
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

/**
 * Where feedback goes. There is no feedback endpoint, so the dialog drafts an
 * email in the person's own mail app; without an address the menu item is
 * hidden rather than pretending to send.
 */
const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL ?? "";

function FeedbackDialog({
	open,
	onOpenChange,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const [kind, setKind] = useState<FeedbackKind>("idea");
	const [message, setMessage] = useState("");
	const close = (): void => {
		onOpenChange(false);
		setMessage("");
		setKind("idea");
	};
	const send = (): void => {
		const label = FEEDBACK_KINDS.find((k) => k.value === kind)?.label;
		const subject = encodeURIComponent(`SecureFabric feedback: ${label}`);
		const body = encodeURIComponent(message.trim());
		window.location.href = `mailto:${SUPPORT_EMAIL}?subject=${subject}&body=${body}`;
		close();
	};
	return (
		<Dialog
			onOpenChange={(next) => (next ? onOpenChange(true) : close())}
			open={open}
		>
			<DialogContent
				description="Opens an email to the SecureFabric team in your mail app."
				footer={
					<>
						<Button onClick={close}>Cancel</Button>
						<Button disabled={!message.trim()} onClick={send} variant="primary">
							Write email
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
	const { me, devMode } = useEnv();
	const email = me.email ?? (devMode ? "development API key" : "");
	const name = me.name ?? (devMode ? "Developer mode" : email);
	const roleLabel = roleInfo(me.role)?.label;
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
						<PersonAvatar seed={email || me.actor_id} />
						<span className="grid min-w-0 flex-1 text-left leading-tight">
							<span className="truncate font-medium">{name}</span>
							<span className="text-muted-foreground truncate text-xs">
								{roleLabel === undefined ? email : `${roleLabel} · ${email}`}
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
							render={<a href={DOCS_URL} rel="noopener" target="_blank" />}
						>
							<BookOpenIcon />
							Docs
						</DropdownMenuItem>
						<DropdownMenuItem
							render={
								<a
									href={`${DOCS_URL}/changelog`}
									rel="noopener"
									target="_blank"
								/>
							}
						>
							<NewspaperIcon />
							Changelog
						</DropdownMenuItem>
						{SUPPORT_EMAIL ? (
							<DropdownMenuItem onClick={() => setFeedbackOpen(true)}>
								<MessageSquareIcon />
								Send feedback
							</DropdownMenuItem>
						) : null}
						<DropdownMenuSeparator />
						<div className="flex items-center justify-between gap-3 px-2 py-1.5">
							<span className="text-sm">Theme</span>
							<ThemeToggle onChange={setTheme} theme={theme} />
						</div>
						<DropdownMenuSeparator />
						<DropdownMenuItem
							onClick={() => {
								if (devMode) {
									toast.info("Developer mode", {
										description:
											"The dashboard is using SF_DEV_API_KEY. Unset it to sign in with WorkOS.",
									});
									return;
								}
								window.location.assign("/logout");
							}}
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
