"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEnv, useHref } from "@/components/shell/env-context";
import {
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
} from "@/components/ui/sidebar";
import { type Focus, SETTINGS_SECTIONS, settingsSection } from "@/lib/nav";

/** Settings takes the sidebar over, with the way back at the top. */
export function FocusedNav({ focus }: { focus: Focus }) {
	const href = useHref();
	const { env } = useEnv();
	const params = useSearchParams();
	const current = settingsSection(params.get("tab"));
	if (focus.kind !== "settings") {
		return null;
	}
	return (
		<>
			<SidebarGroup>
				<SidebarMenu>
					<SidebarMenuItem>
						<SidebarMenuButton
							className="text-muted-foreground hover:text-foreground"
							render={<Link href={href()} />}
							tooltip="Back to app"
						>
							<ArrowLeftIcon />
							<span>Back to app</span>
						</SidebarMenuButton>
					</SidebarMenuItem>
				</SidebarMenu>
			</SidebarGroup>
			<SidebarGroup>
				<SidebarGroupLabel>{`Settings · ${env.name}`}</SidebarGroupLabel>
				<SidebarGroupContent>
					<SidebarMenu>
						{SETTINGS_SECTIONS.map((s) => (
							<SidebarMenuItem key={s.value}>
								<SidebarMenuButton
									isActive={current === s.value}
									render={<Link href={href(`/settings?tab=${s.value}`)} />}
									tooltip={s.label}
								>
									<s.icon />
									<span>{s.label}</span>
								</SidebarMenuButton>
							</SidebarMenuItem>
						))}
					</SidebarMenu>
				</SidebarGroupContent>
			</SidebarGroup>
		</>
	);
}
