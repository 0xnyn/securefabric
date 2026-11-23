"use client";

import { cn } from "@securefabric/ui/lib/utils";
import {
	CopyIcon,
	EllipsisIcon,
	KeyRoundIcon,
	PencilIcon,
	PlusIcon,
	RefreshCwIcon,
	Trash2Icon,
	TriangleAlertIcon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { CopyField, PageBody, PageHeader } from "@/components/common";
import { useEnv } from "@/components/shell/env-context";
import { Button, buttonVariants } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogContent,
	Menu,
	MenuContent,
	MenuItem,
	MenuSeparator,
	MenuTrigger,
	Tooltip,
} from "@/components/ui/overlay";
import {
	Badge,
	Card,
	CardHeader,
	Field,
	Input,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";
import { dateTime, timeAgo } from "@/lib/format";
import {
	createApiKey,
	revokeApiKey,
	rollApiKey,
	updateApiKey,
} from "@/lib/store";
import { type ApiKey, KEY_SCOPES, type KeyScope } from "@/lib/types";

/** What each scope allows, in the words of the endpoints it opens. */
const SCOPE_INFO: Record<KeyScope, { label: string; description: string }> = {
	"actions:write": {
		description: "Isolate devices, create tickets, suspend users.",
		label: "Run actions",
	},
	"connections:write": {
		description: "Create Connect sessions, trigger syncs, delete connections.",
		label: "Manage connections",
	},
	"data:read": {
		description:
			"Read vulnerabilities, devices, alerts and every other unified model.",
		label: "Read data",
	},
	"integrations:write": {
		description: "Enable integrations and change their settings.",
		label: "Manage integrations",
	},
	"keys:write": {
		description: "Create, roll and revoke API keys.",
		label: "Manage API keys",
	},
	"webhooks:write": {
		description: "Add endpoints and rotate the signing secret.",
		label: "Manage webhooks",
	},
};

type Preset = "full" | "read" | "custom";

const PRESETS: { value: Preset; label: string; description: string }[] = [
	{
		description: "Everything this environment's API allows.",
		label: "Full access",
		value: "full",
	},
	{
		description: "Read unified data. Nothing can be changed.",
		label: "Read only",
		value: "read",
	},
	{
		description: "Pick exactly what the key can do.",
		label: "Custom",
		value: "custom",
	},
];

function presetOf(scopes: KeyScope[]): Preset {
	if (scopes.length === KEY_SCOPES.length) {
		return "full";
	}
	if (scopes.length === 1 && scopes[0] === "data:read") {
		return "read";
	}
	return "custom";
}

function scopesFor(preset: Preset, current: KeyScope[]): KeyScope[] {
	if (preset === "full") {
		return [...KEY_SCOPES];
	}
	if (preset === "read") {
		return ["data:read"];
	}
	return current;
}

/**
 * The environment's API keys: one list, each key narrowed by scopes, rather
 * than separate classes of keys for data and for configuration.
 */
export function KeysView() {
	const { env } = useEnv();
	return (
		<>
			<PageHeader
				description={`Keys authenticate requests to the SecureFabric API with the X-API-Key header. Each key only sees ${env.name}'s connections, and its scopes decide what it can do.`}
				title="API keys"
			/>
			<PageBody className="grid max-w-5xl min-w-0 content-start gap-6">
				<KeyList />
			</PageBody>
		</>
	);
}

function ScopeSummary({ scopes }: { scopes: KeyScope[] }) {
	const preset = presetOf(scopes);
	if (preset === "full") {
		return <Badge tone="warn">Full access</Badge>;
	}
	if (preset === "read") {
		return <Badge>Read only</Badge>;
	}
	return (
		<Tooltip
			content={
				<ul className="grid gap-0.5">
					{scopes.map((s) => (
						<li key={s}>{SCOPE_INFO[s].label}</li>
					))}
				</ul>
			}
		>
			<Badge className="cursor-default" tone="accent">
				{scopes.length} {scopes.length === 1 ? "scope" : "scopes"}
			</Badge>
		</Tooltip>
	);
}

type Dialogs =
	| { kind: "create" }
	| { kind: "edit"; key: ApiKey }
	| { kind: "roll"; key: ApiKey }
	| { kind: "revoke"; key: ApiKey }
	| { kind: "reveal"; name: string; value: string; rolled: boolean }
	| null;

function KeyList() {
	const { env } = useEnv();
	const [dialog, setDialog] = useState<Dialogs>(null);
	const count = env.apiKeys.length;
	return (
		<Card className="overflow-hidden">
			<CardHeader
				action={
					<Button
						onClick={() => setDialog({ kind: "create" })}
						size="sm"
						variant="primary"
					>
						<PlusIcon />
						Create key
					</Button>
				}
				description={`${count} ${count === 1 ? "key" : "keys"} in ${env.name}. Full keys are shown once, when they're created or rolled.`}
				title="Keys"
			/>
			<Table className="sm:table-fixed">
				<colgroup>
					<col />
					<col className="hidden w-44 sm:table-column" />
					<col className="w-36" />
					<col className="hidden w-32 lg:table-column" />
					<col className="w-16" />
				</colgroup>
				<thead>
					<tr>
						<Th>Name</Th>
						<Th className="hidden sm:table-cell">Key</Th>
						<Th>Scopes</Th>
						<Th className="hidden lg:table-cell">Last used</Th>
						<Th>
							<span className="sr-only">Actions</span>
						</Th>
					</tr>
				</thead>
				<tbody>
					{env.apiKeys.map((k) => (
						<Tr key={k.id}>
							<Td className="h-16">
								<span className="grid min-w-0 gap-0.5">
									<span className="flex min-w-0 items-center gap-2 font-medium">
										<span className="truncate">{k.name}</span>
										{k.isDefault && k.name !== "Default" ? (
											<Badge className="hidden sm:inline-flex">Default</Badge>
										) : null}
									</span>
									<span
										className="text-muted-foreground truncate text-xs"
										title={dateTime(k.createdAt)}
									>
										Created {timeAgo(k.createdAt)} by {k.createdBy}
									</span>
								</span>
							</Td>
							<Td className="hidden sm:table-cell">
								<span className="text-code text-muted-foreground font-mono">
									{k.preview}
								</span>
							</Td>
							<Td>
								<ScopeSummary scopes={k.scopes} />
							</Td>
							<Td className="text-muted-foreground hidden lg:table-cell">
								{k.lastUsedAt ? timeAgo(k.lastUsedAt) : "Never"}
							</Td>
							<Td className="text-right">
								<KeyActions apiKey={k} onOpen={setDialog} />
							</Td>
						</Tr>
					))}
				</tbody>
			</Table>
			<KeyDialogs
				close={() => setDialog(null)}
				dialog={dialog}
				onOpen={setDialog}
			/>
		</Card>
	);
}

function KeyActions({
	apiKey,
	onOpen,
}: {
	apiKey: ApiKey;
	onOpen: (dialog: Dialogs) => void;
}) {
	const { env } = useEnv();
	return (
		<Menu>
			<MenuTrigger
				aria-label={`Actions for ${apiKey.name}`}
				className={buttonVariants({ size: "icon-sm", variant: "ghost" })}
			>
				<EllipsisIcon />
			</MenuTrigger>
			<MenuContent align="end" className="w-52">
				{apiKey.isDefault ? (
					<MenuItem
						onClick={() => {
							navigator.clipboard.writeText(env.keys.secret);
							toast.success("Key copied");
						}}
					>
						<CopyIcon />
						Copy key
					</MenuItem>
				) : null}
				<MenuItem onClick={() => onOpen({ key: apiKey, kind: "edit" })}>
					<PencilIcon />
					Edit name and scopes
				</MenuItem>
				<MenuItem onClick={() => onOpen({ key: apiKey, kind: "roll" })}>
					<RefreshCwIcon />
					Roll key
				</MenuItem>
				{apiKey.isDefault ? null : (
					<>
						<MenuSeparator />
						<MenuItem
							className="text-destructive [&_svg]:text-destructive"
							onClick={() => onOpen({ key: apiKey, kind: "revoke" })}
						>
							<Trash2Icon />
							Revoke key
						</MenuItem>
					</>
				)}
			</MenuContent>
		</Menu>
	);
}

function KeyDialogs({
	dialog,
	close,
	onOpen,
}: {
	dialog: Dialogs;
	close: () => void;
	onOpen: (dialog: Dialogs) => void;
}) {
	const { env } = useEnv();
	return (
		<Dialog
			onOpenChange={(next) => {
				if (!next) {
					close();
				}
			}}
			open={dialog !== null}
		>
			{dialog?.kind === "create" ? (
				<KeyForm
					onCancel={close}
					onSubmit={async (name, scopes) => {
						const value = await createApiKey(env.slug, name, scopes);
						onOpen({ kind: "reveal", name, rolled: false, value });
					}}
					submitLabel="Create key"
					title="Create API key"
				/>
			) : null}
			{dialog?.kind === "edit" ? (
				<KeyForm
					initial={dialog.key}
					onCancel={close}
					onSubmit={(name, scopes) => {
						updateApiKey(env.slug, dialog.key.id, { name, scopes });
						toast.success("Key updated");
						close();
					}}
					submitLabel="Save"
					title={`Edit ${dialog.key.name}`}
				/>
			) : null}
			{dialog?.kind === "roll" ? (
				<RollDialog apiKey={dialog.key} close={close} onOpen={onOpen} />
			) : null}
			{dialog?.kind === "revoke" ? (
				<DialogContent
					description="Requests made with it start failing with 401 straight away. This can't be undone."
					footer={
						<>
							<Button onClick={close}>Cancel</Button>
							<Button
								onClick={() => {
									revokeApiKey(env.slug, dialog.key.id);
									toast.success(`${dialog.key.name} revoked`);
									close();
								}}
								variant="destructive"
							>
								Revoke key
							</Button>
						</>
					}
					title={`Revoke ${dialog.key.name}?`}
				/>
			) : null}
			{dialog?.kind === "reveal" ? (
				<DialogContent
					description="Copy it now and keep it somewhere safe, such as your secrets manager. You won't be able to see it again."
					footer={
						<Button onClick={close} variant="primary">
							Done
						</Button>
					}
					title={
						dialog.rolled ? `${dialog.name} rolled` : `${dialog.name} created`
					}
				>
					<div className="grid gap-3">
						<CopyField label="API key" value={dialog.value} />
						<p className="text-ds-warn-text flex items-start gap-2 text-xs">
							<TriangleAlertIcon className="mt-0.5 size-3.5 shrink-0" />
							Only the first and last characters are kept after you close this.
						</p>
					</div>
				</DialogContent>
			) : null}
		</Dialog>
	);
}

function RollDialog({
	apiKey,
	close,
	onOpen,
}: {
	apiKey: ApiKey;
	close: () => void;
	onOpen: (dialog: Dialogs) => void;
}) {
	const { env } = useEnv();
	const grace =
		"The current value keeps working for 24 hours so you can deploy the new one.";
	return (
		<DialogContent
			description={
				apiKey.isDefault
					? `${grace} Code samples in the dashboard switch to the new key straight away.`
					: grace
			}
			footer={
				<>
					<Button onClick={close}>Cancel</Button>
					<Button
						onClick={async () => {
							const value = await rollApiKey(env.slug, apiKey.id);
							onOpen({
								kind: "reveal",
								name: apiKey.name,
								rolled: true,
								value,
							});
						}}
						variant="destructive"
					>
						Roll key
					</Button>
				</>
			}
			title={`Roll ${apiKey.name}?`}
		/>
	);
}

function KeyForm({
	title,
	submitLabel,
	initial,
	onCancel,
	onSubmit,
}: {
	title: string;
	submitLabel: string;
	initial?: ApiKey;
	onCancel: () => void;
	onSubmit: (name: string, scopes: KeyScope[]) => void;
}) {
	const [name, setName] = useState(initial?.name ?? "");
	const [scopes, setScopes] = useState<KeyScope[]>(
		initial?.scopes ?? [...KEY_SCOPES]
	);
	const [preset, setPreset] = useState<Preset>(presetOf(scopes));
	const valid = name.trim().length > 0 && scopes.length > 0;
	const submit = (): void => {
		if (valid) {
			onSubmit(name.trim(), scopes);
		}
	};
	return (
		<DialogContent
			className="max-w-lg"
			footer={
				<>
					<Button onClick={onCancel}>Cancel</Button>
					<Button disabled={!valid} onClick={submit} variant="primary">
						{submitLabel}
					</Button>
				</>
			}
			title={title}
		>
			<form
				className="grid gap-5"
				onSubmit={(e) => {
					e.preventDefault();
					submit();
				}}
			>
				<Field
					help="Where it's used, so whoever rolls it knows what to update."
					htmlFor="key-name"
					label="Name"
				>
					<Input
						autoFocus
						id="key-name"
						onChange={(e) => setName(e.target.value)}
						placeholder="e.g. Production backend"
						value={name}
					/>
				</Field>
				<Field label="Access">
					<div className="grid gap-2 sm:grid-cols-3">
						{PRESETS.map((p) => (
							<button
								aria-pressed={preset === p.value}
								className={cn(
									"grid content-start gap-0.5 rounded-lg border p-3 text-left transition-colors",
									preset === p.value
										? "border-ds-primary bg-ds-primary/5"
										: "border-border hover:bg-muted"
								)}
								key={p.value}
								onClick={() => {
									setPreset(p.value);
									setScopes(scopesFor(p.value, scopes));
								}}
								type="button"
							>
								<span className="text-sm font-medium">{p.label}</span>
								<span className="text-muted-foreground text-xs">
									{p.description}
								</span>
							</button>
						))}
					</div>
				</Field>
				{preset === "custom" ? (
					<ScopeChecklist onChange={setScopes} value={scopes} />
				) : null}
				{initial ? null : (
					<p className="text-muted-foreground flex items-center gap-2 text-xs">
						<KeyRoundIcon className="size-3.5" />
						The key will only work in this environment.
					</p>
				)}
			</form>
		</DialogContent>
	);
}

function ScopeChecklist({
	value,
	onChange,
}: {
	value: KeyScope[];
	onChange: (scopes: KeyScope[]) => void;
}) {
	return (
		<fieldset className="border-border divide-border grid divide-y rounded-lg border">
			<legend className="sr-only">Scopes</legend>
			{KEY_SCOPES.map((s) => (
				<label className="flex items-start gap-3 px-4 py-3" key={s}>
					<Checkbox
						checked={value.includes(s)}
						className="mt-0.5"
						onCheckedChange={(on) =>
							onChange(
								on
									? KEY_SCOPES.filter((x) => x === s || value.includes(x))
									: value.filter((x) => x !== s)
							)
						}
					/>
					<span className="grid gap-0.5">
						<span className="flex items-center gap-2 text-sm font-medium">
							{SCOPE_INFO[s].label}
							<span className="text-muted-foreground font-mono text-xs font-normal">
								{s}
							</span>
						</span>
						<span className="text-muted-foreground text-xs">
							{SCOPE_INFO[s].description}
						</span>
					</span>
				</label>
			))}
		</fieldset>
	);
}
