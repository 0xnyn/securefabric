"use client";

import { cn } from "@securefabric/ui/lib/utils";
import { FlaskConicalIcon, LockIcon, Trash2Icon } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import {
	CopyField,
	PageBody,
	PageHeader,
	PersonAvatar,
	ProviderLogo,
} from "@/components/common";
import { useEnv } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { Select, Switch } from "@/components/ui/overlay";
import {
	Badge,
	Card,
	CardFooter,
	CardHeader,
	Field,
	Input,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";
import { WebhooksSection } from "@/components/views/webhooks";
import { providerOrThrow } from "@/lib/catalog";
import { timeAgo } from "@/lib/format";
import { SETTINGS_SECTIONS, settingsSection } from "@/lib/nav";
import {
	deleteEnvironment,
	inviteMember,
	removeMember,
	removeVariable,
	setMemberRole,
	setVariable,
	updateEnvironment,
} from "@/lib/store";
import type { ConnectTheme, Role } from "@/lib/types";

/**
 * The sidebar lists the sections (shell/focused-nav.tsx, SettingsFocus) and
 * writes `?tab=`; the page only renders the one selected.
 */
export function SettingsView() {
	const params = useSearchParams();
	const section = settingsSection(params.get("tab"));
	const meta = SETTINGS_SECTIONS.find((s) => s.value === section);
	return (
		<>
			<PageHeader
				description={meta?.description}
				title={meta?.label ?? "Settings"}
			/>
			{/* Left-aligned beside the sidebar's sections, at the same width as
			    Keys so the content edge doesn't move between them. */}
			<PageBody className="grid max-w-5xl min-w-0 content-start gap-6">
				{section === "general" ? <GeneralSection /> : null}
				{section === "webhooks" ? <WebhooksSection /> : null}
				{section === "connect" ? <ConnectSection /> : null}
				{section === "variables" ? <VariablesSection /> : null}
				{section === "team" ? <TeamSection /> : null}
			</PageBody>
		</>
	);
}

function GeneralSection() {
	const { env, workspace } = useEnv();
	const router = useRouter();
	const [name, setName] = useState(env.name);
	const last = workspace.environments.length === 1;
	return (
		<>
			<Card>
				<CardHeader
					description="Shown in the environment switcher and on logs."
					title="Environment name"
				/>
				<div className="px-5 py-4 sm:w-96">
					<Input
						aria-label="Environment name"
						onChange={(e) => setName(e.target.value)}
						value={name}
					/>
				</div>
				<CardFooter>
					<span>
						Slug{" "}
						<span className="text-code text-foreground font-mono">
							{env.slug}
						</span>{" "}
						· created {timeAgo(env.createdAt)}
					</span>
					<Button
						disabled={!name.trim() || name === env.name}
						onClick={() => {
							updateEnvironment(env.slug, { name: name.trim() });
							toast.success("Environment renamed");
						}}
						size="sm"
						variant="primary"
					>
						Save
					</Button>
				</CardFooter>
			</Card>
			<Card>
				<div className="flex items-start justify-between gap-6 px-5 py-4">
					<div className="grid gap-1">
						<p className="text-sm font-medium">Production environment</p>
						<p className="text-muted-foreground text-sm">
							Production environments issue live keys, hide credentials from
							Support members, limit Contributors to read-only, and disable
							sandbox connections by default.
						</p>
					</div>
					<Switch
						ariaLabel="Production environment"
						checked={env.isProduction}
						onChange={(v) => {
							updateEnvironment(env.slug, { isProduction: v });
							toast.success(
								v ? "Marked as production" : "Marked as non-production"
							);
						}}
					/>
				</div>
			</Card>
			<Card>
				<CardHeader
					description="Register this redirect URI in the vendor app for OAuth integrations such as Microsoft Defender, Entra ID and Jira."
					title="OAuth callback URL"
				/>
				<div className="px-5 py-4">
					<CopyField label="Callback URL" value={env.callbackUrl} />
				</div>
			</Card>
			<Card className="border-destructive/30">
				<CardHeader
					description="Deletes every integration, connection, key, webhook and log in this environment. Stored credentials are destroyed immediately."
					title="Delete environment"
				/>
				<CardFooter>
					<span>
						{last
							? "You can't delete the only environment."
							: "This can't be undone."}
					</span>
					<Button
						disabled={last}
						onClick={() => {
							const next = workspace.environments.find(
								(e) => e.slug !== env.slug
							);
							deleteEnvironment(env.slug);
							toast.success(`${env.name} deleted`);
							router.push(`/${next?.slug ?? "dev"}`);
						}}
						size="sm"
						variant="destructive"
					>
						<Trash2Icon />
						Delete {env.name}
					</Button>
				</CardFooter>
			</Card>
		</>
	);
}

function ConnectPreview({
	theme,
	brandName,
	hideBadge,
}: {
	theme: ConnectTheme;
	brandName: string;
	hideBadge: boolean;
}) {
	const { env } = useEnv();
	const dark = theme === "dark";
	return (
		<section
			aria-label="Preview"
			className={cn(
				"border-border bg-ds-shell grid min-h-96 content-center rounded-xl border p-8 lg:sticky lg:top-6",
				dark && "dark"
			)}
		>
			<p className="text-ds-muted mb-4 text-center text-xs font-medium">
				Preview
			</p>
			<div className="border-border bg-ds-card text-ds-fg shadow-float mx-auto grid w-full max-w-sm gap-4 rounded-xl border p-5">
				<div className="grid gap-1">
					<p className="font-semibold">Connect your security tools</p>
					<p className="text-ds-muted text-xs">
						{brandName || "Your app"} will read data from the tool you choose.
						Credentials are encrypted and never shared.
					</p>
				</div>
				<ul className="grid gap-1.5">
					{env.integrations.slice(0, 4).map((i) => (
						<li
							className="border-ds-line flex items-center gap-2.5 rounded-md border px-3 py-2 text-sm"
							key={i.id}
						>
							<ProviderLogo provider={i.provider} size={20} />
							{providerOrThrow(i.provider).name}
						</li>
					))}
				</ul>
				{hideBadge ? null : (
					<p className="text-2xs text-ds-muted flex items-center justify-center gap-1">
						<LockIcon className="size-3" />
						Secured by SecureFabric
					</p>
				)}
			</div>
		</section>
	);
}

function ConnectSection() {
	const { env } = useEnv();
	const [brandName, setBrandName] = useState(env.connect.brandName);
	const save = (patch: Partial<typeof env.connect>): void => {
		updateEnvironment(env.slug, { connect: { ...env.connect, ...patch } });
	};
	return (
		<div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
			<Card>
				<CardHeader
					description="How SecureFabric Connect looks when your customers link their tools."
					title="Appearance"
				/>
				<div className="grid content-start gap-5 px-5 py-5">
					<Field htmlFor="brand" label="Brand name">
						<Input
							id="brand"
							onBlur={() => {
								if (brandName !== env.connect.brandName) {
									save({ brandName });
									toast.success("Brand name saved");
								}
							}}
							onChange={(e) => setBrandName(e.target.value)}
							value={brandName}
						/>
					</Field>
					<Field label="Theme">
						<Select
							ariaLabel="Theme"
							onChange={(v) => save({ theme: v })}
							options={[
								{ label: "Match the user's system", value: "system" },
								{ label: "Light", value: "light" },
								{ label: "Dark", value: "dark" },
							]}
							value={env.connect.theme}
						/>
					</Field>
					<div className="flex items-center justify-between gap-4">
						<div className="grid gap-0.5">
							<span className="text-sm font-medium">
								Hide "Secured by SecureFabric"
							</span>
							<span className="text-muted-foreground text-xs">
								Available on Growth and Enterprise.
							</span>
						</div>
						<Switch
							ariaLabel="Hide badge"
							checked={env.connect.hideBadge}
							onChange={(v) => save({ hideBadge: v })}
						/>
					</div>
					<p className="bg-ds-accent/5 text-muted-foreground flex items-start gap-2 rounded-md p-3 text-xs">
						<FlaskConicalIcon className="text-ds-accent mt-0.5 size-3.5 shrink-0" />
						Integrations that allow sandbox connections show a "Try with sample
						data" option, so prospects can see your product before they hand
						over credentials.
					</p>
				</div>
			</Card>
			<ConnectPreview
				brandName={brandName}
				hideBadge={env.connect.hideBadge}
				theme={env.connect.theme}
			/>
		</div>
	);
}

const VAR_KEY = /[^A-Z0-9_]/gu;

function VariablesSection() {
	const { env } = useEnv();
	const [key, setKey] = useState("");
	const [value, setValue] = useState("");
	const [secret, setSecret] = useState(false);
	return (
		<Card className="overflow-hidden">
			<CardHeader
				description="Values your custom sync logic and actions read at runtime. Secret values are encrypted and write-only."
				title="Environment variables"
			/>
			{env.variables.length ? (
				<Table>
					<thead>
						<tr>
							<Th>Key</Th>
							<Th>Value</Th>
							<Th className="w-12" />
						</tr>
					</thead>
					<tbody>
						{env.variables.map((v) => (
							<Tr key={v.key}>
								<Td className="text-code font-mono">{v.key}</Td>
								<Td className="text-code text-muted-foreground font-mono">
									{v.secret ? (
										<span className="inline-flex items-center gap-1.5">
											<LockIcon className="size-3" />
											••••••••
										</span>
									) : (
										v.value
									)}
								</Td>
								<Td>
									<Button
										aria-label={`Delete ${v.key}`}
										onClick={() => removeVariable(env.slug, v.key)}
										size="icon-sm"
										variant="ghost"
									>
										<Trash2Icon />
									</Button>
								</Td>
							</Tr>
						))}
					</tbody>
				</Table>
			) : (
				<p className="text-muted-foreground px-5 py-6 text-sm">
					No variables in {env.name}.
				</p>
			)}
			<form
				className="border-border bg-ds-shell flex flex-col gap-2 border-t px-5 py-4 md:flex-row md:items-center"
				onSubmit={(e) => {
					e.preventDefault();
					if (!(key && value)) {
						return;
					}
					setVariable(env.slug, key, value, secret);
					setKey("");
					setValue("");
					toast.success(`${key} saved`);
				}}
			>
				<Input
					aria-label="Key"
					className="font-mono md:w-56"
					onChange={(e) =>
						setKey(e.target.value.toUpperCase().replace(VAR_KEY, "_"))
					}
					placeholder="KEY"
					value={key}
				/>
				<Input
					aria-label="Value"
					className="font-mono"
					onChange={(e) => setValue(e.target.value)}
					placeholder="value"
					type={secret ? "password" : "text"}
					value={value}
				/>
				<span className="flex shrink-0 items-center gap-2 text-sm">
					<Switch checked={secret} id="var-secret" onChange={setSecret} />
					<label htmlFor="var-secret">Secret</label>
				</span>
				<Button disabled={!(key && value)} type="submit">
					Add
				</Button>
			</form>
		</Card>
	);
}

const ROLES: { value: Role; description: string }[] = [
	{
		description:
			"Everything, including production credentials, billing and team.",
		value: "Full access",
	},
	{
		description: "Read and write in non-production environments only.",
		value: "Contributor",
	},
	{
		description: "Read-only in production; can trigger syncs. No credentials.",
		value: "Support",
	},
];

function TeamSection() {
	const { workspace } = useEnv();
	const [email, setEmail] = useState("");
	const [role, setRole] = useState<Role>("Contributor");
	return (
		<Card className="overflow-hidden">
			<CardHeader
				description={`Members of ${workspace.team.name}. Team access applies to every environment.`}
				title="Team"
			/>
			<Table>
				<thead>
					<tr>
						<Th>Member</Th>
						<Th className="w-48">Role</Th>
						<Th className="hidden sm:table-cell">Joined</Th>
						<Th className="w-12" />
					</tr>
				</thead>
				<tbody>
					{workspace.members.map((m) => (
						<Tr key={m.id}>
							<Td>
								<div className="flex items-center gap-3 py-2">
									<PersonAvatar seed={m.email} />
									<span className="grid">
										<span className="font-medium">{m.name}</span>
										<span className="text-muted-foreground text-xs">
											{m.email}
										</span>
									</span>
								</div>
							</Td>
							<Td>
								{m.name === "You" ? (
									<span className="text-sm">{m.role}</span>
								) : (
									<Select
										ariaLabel={`Role for ${m.email}`}
										onChange={(r) => setMemberRole(m.id, r)}
										options={ROLES.map((r) => ({
											description: r.description,
											label: r.value,
											value: r.value,
										}))}
										size="sm"
										value={m.role}
									/>
								)}
							</Td>
							<Td className="text-muted-foreground hidden sm:table-cell">
								{m.joinedAt ? timeAgo(m.joinedAt) : <Badge>Invited</Badge>}
							</Td>
							<Td>
								{m.name === "You" ? null : (
									<Button
										aria-label={`Remove ${m.email}`}
										onClick={() => removeMember(m.id)}
										size="icon-sm"
										variant="ghost"
									>
										<Trash2Icon />
									</Button>
								)}
							</Td>
						</Tr>
					))}
				</tbody>
			</Table>
			<form
				className="border-border bg-ds-shell flex flex-col gap-2 border-t px-5 py-4 sm:flex-row"
				onSubmit={(e) => {
					e.preventDefault();
					if (!email.includes("@")) {
						return;
					}
					inviteMember(email, role);
					setEmail("");
					toast.success(`Invitation sent to ${email}`);
				}}
			>
				<Input
					aria-label="Email"
					onChange={(e) => setEmail(e.target.value)}
					placeholder="teammate@company.com"
					type="email"
					value={email}
				/>
				<div className="sm:w-44">
					<Select
						ariaLabel="Role"
						onChange={setRole}
						options={ROLES.map((r) => ({ label: r.value, value: r.value }))}
						value={role}
					/>
				</div>
				<Button disabled={!email} type="submit" variant="primary">
					Invite
				</Button>
			</form>
		</Card>
	);
}
