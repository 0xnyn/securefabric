"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { ProviderLogo } from "@/components/common";
import { useEnv } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, Select, Switch } from "@/components/ui/overlay";
import { Field, Input } from "@/components/ui/primitives";
import { MODELS, type ModelKey, type Provider } from "@/lib/catalog";
import { enableIntegration } from "@/lib/store";
import { FREQUENCY_LABELS, type SyncFrequency } from "@/lib/types";

const KEY_CHARS = /[^a-z0-9-]/gu;

export function EnableIntegrationDialog({
	provider,
	open,
	onOpenChange,
}: {
	provider: Provider;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const { env } = useEnv();
	const router = useRouter();
	const taken = env.integrations.some((i) => i.id === provider.slug);
	const [key, setKey] = useState(taken ? `${provider.slug}-2` : provider.slug);
	const [models, setModels] = useState<ModelKey[]>(provider.models);
	const [frequency, setFrequency] = useState<SyncFrequency>(
		provider.models.includes("detections") ? "15m" : "1h"
	);
	const [sandbox, setSandbox] = useState(!env.isProduction);
	const [writes, setWrites] = useState<string[]>([]);

	const toggle = <T,>(list: T[], item: T): T[] =>
		list.includes(item) ? list.filter((x) => x !== item) : [...list, item];

	const submit = async (e: React.FormEvent): Promise<void> => {
		e.preventDefault();
		const id = await enableIntegration(env.slug, provider.slug, {
			allowSandbox: sandbox,
			id: key,
			models,
			syncFrequency: frequency,
			writeScopes: writes,
		});
		onOpenChange(false);
		toast.success(`${provider.name} enabled in ${env.name}`, {
			action: {
				label: sandbox ? "Connect sandbox" : "Add connection",
				onClick: () =>
					router.push(`/${env.slug}/connections?new=1&integration=${id}`),
			},
			description: `Integration ID: ${id}`,
		});
		router.push(`/${env.slug}/integrations/${id}`);
	};

	return (
		<Dialog onOpenChange={onOpenChange} open={open}>
			<DialogContent
				className="max-w-xl"
				description={`Configure how ${provider.name} syncs in ${env.name}. You can change all of this later.`}
				footer={
					<>
						<Button onClick={() => onOpenChange(false)}>Cancel</Button>
						<Button
							disabled={
								!key || (models.length === 0 && provider.models.length > 0)
							}
							form="enable-integration"
							type="submit"
							variant="primary"
						>
							Enable integration
						</Button>
					</>
				}
				title={
					<span className="flex items-center gap-3">
						<ProviderLogo provider={provider} size={28} />
						Enable {provider.name}
					</span>
				}
			>
				<form className="grid gap-5" id="enable-integration" onSubmit={submit}>
					<Field
						help="Pass this as integrationId when creating connect sessions. Lowercase letters, numbers and dashes."
						htmlFor="int-key"
						label="Integration ID"
					>
						<Input
							className="font-mono"
							id="int-key"
							onChange={(e) =>
								setKey(e.target.value.toLowerCase().replace(KEY_CHARS, ""))
							}
							value={key}
						/>
					</Field>
					{provider.models.length > 0 ? (
						<fieldset className="grid gap-2">
							<legend className="mb-2 text-sm font-medium">
								Models to sync
							</legend>
							{provider.models.map((m) => (
								<label
									className="border-border hover:bg-ds-shell flex cursor-pointer items-start gap-3 rounded-md border p-3"
									key={m}
								>
									<input
										checked={models.includes(m)}
										className="accent-primary mt-0.5"
										onChange={() => setModels(toggle(models, m))}
										type="checkbox"
									/>
									<span className="grid gap-0.5">
										<span className="flex items-center gap-2 text-sm">
											<span className="font-mono">{MODELS[m].name}</span>
											<span className="text-2xs text-muted-foreground font-mono">
												{MODELS[m].scope}
											</span>
										</span>
										<span className="text-muted-foreground text-xs">
											{MODELS[m].description}
										</span>
									</span>
								</label>
							))}
						</fieldset>
					) : null}
					{provider.writeActions.length > 0 ? (
						<fieldset className="grid gap-2">
							<legend className="mb-2 text-sm font-medium">
								Write actions
							</legend>
							<p className="text-muted-foreground -mt-1 mb-1 text-xs">
								Customers approve each scope in SecureFabric Connect and can
								revoke it at any time.
							</p>
							{provider.writeActions.map((a) => (
								<label
									className="flex cursor-pointer items-center gap-3 text-sm"
									key={a.scope}
								>
									<input
										checked={writes.includes(a.scope)}
										className="accent-primary"
										onChange={() => setWrites(toggle(writes, a.scope))}
										type="checkbox"
									/>
									{a.name}
									<span className="text-2xs text-muted-foreground font-mono">
										{a.scope}
									</span>
								</label>
							))}
						</fieldset>
					) : null}
					<Field
						help="Incremental: only records changed since the last sync are fetched."
						label="Sync frequency"
					>
						<Select
							ariaLabel="Sync frequency"
							onChange={setFrequency}
							options={(Object.keys(FREQUENCY_LABELS) as SyncFrequency[]).map(
								(f) => ({ label: FREQUENCY_LABELS[f], value: f })
							)}
							value={frequency}
						/>
					</Field>
					<div className="border-border flex items-start justify-between gap-4 rounded-lg border p-4">
						<div className="grid gap-1">
							<label className="text-sm font-medium" htmlFor="int-sandbox">
								Allow sandbox connections
							</label>
							<p className="text-muted-foreground text-sm">
								Connect without vendor credentials and read realistic generated
								data.
								{env.isProduction ? " Not recommended in production." : ""}
							</p>
						</div>
						<Switch checked={sandbox} id="int-sandbox" onChange={setSandbox} />
					</div>
				</form>
			</DialogContent>
		</Dialog>
	);
}
