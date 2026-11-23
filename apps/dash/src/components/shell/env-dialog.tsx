"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, Select, Switch } from "@/components/ui/overlay";
import { Field, Input } from "@/components/ui/primitives";
import { createEnvironment, slugifyEnv } from "@/lib/store";
import type { Workspace } from "@/lib/types";

/** Opened from the environment switcher and from the ⌘K palette. */
export function CreateEnvironmentDialog({
	open,
	onOpenChange,
	workspace,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	workspace: Workspace;
}) {
	const router = useRouter();
	const [name, setName] = useState("Staging");
	const [slug, setSlug] = useState("staging");
	const [slugEdited, setSlugEdited] = useState(false);
	const [isProduction, setIsProduction] = useState(false);
	const [copyFrom, setCopyFrom] = useState<string>("dev");
	const submit = async (e: React.FormEvent): Promise<void> => {
		e.preventDefault();
		if (!name.trim()) {
			return;
		}
		const created = await createEnvironment({
			copyFrom: copyFrom === "none" ? null : copyFrom,
			isProduction,
			name: name.trim(),
			slug: slugifyEnv(slug || name),
		});
		onOpenChange(false);
		toast.success(`Environment "${name}" created`, {
			description: "It has its own keys, integrations, connections and logs.",
		});
		router.push(`/${created}`);
	};
	return (
		<Dialog onOpenChange={onOpenChange} open={open}>
			<DialogContent
				description="Environments isolate keys, integrations, connections, webhooks and logs. Use one per stage of your pipeline."
				footer={
					<>
						<Button onClick={() => onOpenChange(false)}>Cancel</Button>
						<Button form="create-env" type="submit" variant="primary">
							Create environment
						</Button>
					</>
				}
				title="Create environment"
			>
				<form className="grid gap-5" id="create-env" onSubmit={submit}>
					<Field htmlFor="env-name" label="Name">
						<Input
							autoFocus
							id="env-name"
							onChange={(e) => {
								setName(e.target.value);
								if (!slugEdited) {
									setSlug(slugifyEnv(e.target.value));
								}
							}}
							value={name}
						/>
					</Field>
					<Field
						help={`URLs and API references use the slug: /${slug || "…"}/connections`}
						htmlFor="env-slug"
						label="Slug"
					>
						<Input
							className="font-mono"
							id="env-slug"
							onChange={(e) => {
								setSlugEdited(true);
								setSlug(slugifyEnv(e.target.value));
							}}
							value={slug}
						/>
					</Field>
					<Field
						help="Copies enabled integrations, environment variables and Connect branding. Connections and keys are never copied."
						label="Start from"
					>
						<Select
							ariaLabel="Copy settings from"
							onChange={setCopyFrom}
							options={[
								{ label: "Empty environment", value: "none" },
								...workspace.environments.map((e) => ({
									label: `Copy from ${e.name}`,
									value: e.slug,
								})),
							]}
							value={copyFrom}
						/>
					</Field>
					<div className="border-border flex items-start justify-between gap-4 rounded-lg border p-4">
						<div className="grid gap-1">
							<label className="text-sm font-medium" htmlFor="env-prod">
								Production environment
							</label>
							<p className="text-muted-foreground text-sm">
								Issues <span className="text-code font-mono">sk_live_</span>{" "}
								keys, disables sandbox connections and limits Contributors to
								read-only.
							</p>
						</div>
						<Switch
							checked={isProduction}
							id="env-prod"
							onChange={setIsProduction}
						/>
					</div>
				</form>
			</DialogContent>
		</Dialog>
	);
}
