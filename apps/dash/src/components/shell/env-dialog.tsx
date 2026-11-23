"use client";

import { unwrap } from "@securefabric/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { errorText } from "@/components/kit";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, Switch } from "@/components/ui/overlay";
import { Field, Input } from "@/components/ui/primitives";
import { api } from "@/lib/api";

const SLUG = /[^a-z0-9]+/gu;

export function slugifyEnv(value: string): string {
	return (
		value
			.toLowerCase()
			.replace(SLUG, "-")
			.replace(/^-+|-+$/gu, "")
			.slice(0, 40) || "env"
	);
}

/** Opened from the environment switcher and from the ⌘K palette (`POST /v1/environments`). */
export function CreateEnvironmentDialog({
	open,
	onOpenChange,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [name, setName] = useState("Staging");
	const [slug, setSlug] = useState("staging");
	const [slugEdited, setSlugEdited] = useState(false);
	const [isProduction, setIsProduction] = useState(false);
	const create = useMutation({
		mutationFn: () =>
			unwrap(
				api.POST("/v1/environments", {
					body: {
						is_production: isProduction,
						name: name.trim(),
						slug: slugifyEnv(slug || name),
					},
				})
			),
		onError: (e) =>
			toast.error("Couldn't create the environment", {
				description: errorText(e),
			}),
		onSuccess: async (env) => {
			await queryClient.invalidateQueries({ queryKey: ["environments"] });
			onOpenChange(false);
			toast.success(`Environment "${env.name}" created`, {
				description:
					"It has its own keys, vault key, integrations, connections and logs.",
			});
			router.push(`/${env.slug}`);
		},
	});
	return (
		<Dialog onOpenChange={onOpenChange} open={open}>
			<DialogContent
				description="Environments isolate keys, data, webhooks and the vault key. Use one per stage of your pipeline."
				footer={
					<>
						<Button onClick={() => onOpenChange(false)}>Cancel</Button>
						<Button
							disabled={create.isPending}
							form="create-env"
							type="submit"
							variant="primary"
						>
							Create environment
						</Button>
					</>
				}
				title="Create environment"
			>
				<form
					className="grid gap-5"
					id="create-env"
					onSubmit={(e) => {
						e.preventDefault();
						if (name.trim()) {
							create.mutate();
						}
					}}
				>
					<Field htmlFor="env-name" label="Name">
						<Input
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
						help="Used in URLs and the X-Environment-Id header."
						htmlFor="env-slug"
						label="Slug"
					>
						<Input
							className="font-mono"
							id="env-slug"
							onChange={(e) => {
								setSlugEdited(true);
								setSlug(e.target.value);
							}}
							value={slug}
						/>
					</Field>
					<div className="flex items-center justify-between gap-4">
						<div className="grid gap-0.5">
							<span className="text-sm font-medium">Production</span>
							<span className="text-muted-foreground text-xs">
								API keys are issued as sfk_live_….
							</span>
						</div>
						<Switch
							ariaLabel="Production"
							checked={isProduction}
							onChange={setIsProduction}
						/>
					</div>
				</form>
			</DialogContent>
		</Dialog>
	);
}
