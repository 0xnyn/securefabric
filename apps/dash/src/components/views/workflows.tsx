"use client";

import { isApiError, type ValidationResponseError } from "@securefabric/client";
import { cn } from "@securefabric/ui/lib/utils";
import { formatDistanceToNowStrict } from "date-fns";
import { PlayIcon, SquareIcon, Trash2Icon, WorkflowIcon } from "lucide-react";
import { type FormEvent, useId, useState } from "react";
import { toast } from "sonner";
import { PageBody, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import {
	Badge,
	Card,
	CardFooter,
	CardHeader,
	Dot,
	EmptyState,
	Field,
	Input,
	Mono,
	Table,
	Td,
	Th,
	type Tone,
	Tr,
} from "@/components/ui/primitives";
import { useApiReadiness } from "@/hooks/queries/health";
import {
	type Queue,
	type TaskState,
	TERMINAL_STATES,
	useCancelTask,
	useTask,
} from "@/hooks/queries/tasks";
import {
	type ProvisionTenantInput,
	type TaskAccepted,
	type TenantPlan,
	useProvisionTenant,
} from "@/hooks/queries/tenants";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { API_URL } from "@/lib/api";

/**
 * Exhaustive over the API's task states. `TaskState` is generated from
 * absurd_sdk's `TaskResultState` literal, so if the backend grows a state
 * this record stops compiling until the UI handles it.
 */
const STATE_TONES: Record<TaskState, Tone> = {
	cancelled: "warn",
	completed: "ok",
	failed: "error",
	pending: "neutral",
	running: "busy",
	sleeping: "accent",
};

const PLANS: TenantPlan[] = ["free", "pro", "enterprise"];

const RUNS_STORAGE_KEY = "securefabric-workflow-runs";
const MAX_RUNS = 25;

interface Run {
	accepted: TaskAccepted;
	plan: TenantPlan;
	startedAt: number;
	tenantId: string;
}

export function WorkflowsView() {
	const [runs, setRuns] = useLocalStorage<Run[]>(RUNS_STORAGE_KEY, []);

	const addRun = (run: Run): void =>
		setRuns((prev) =>
			[
				run,
				...prev.filter((r) => r.accepted.task_id !== run.accepted.task_id),
			].slice(0, MAX_RUNS)
		);

	return (
		<>
			<PageHeader
				actions={<ApiStatus />}
				description={
					<>
						Spawn the <Mono>provision-tenant</Mono> durable workflow on the API
						and watch the worker run it: a step, a durable sleep, then
						activation. Every request and response here is typed from the
						FastAPI schema.
					</>
				}
				title="Workflows"
			/>
			<PageBody className="grid items-start gap-6 xl:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
				<ProvisionTenantCard onSpawned={addRun} />
				<RunsCard onClear={() => setRuns([])} runs={runs} />
			</PageBody>
		</>
	);
}

function ApiStatus() {
	const { data, isError, isPending } = useApiReadiness();
	let tone: Tone = "busy";
	let label = "Checking API";
	if (isError) {
		tone = "error";
		label = "API unreachable";
	} else if (!isPending) {
		const ok = data.status === "ok";
		tone = ok ? "ok" : "warn";
		label = ok ? "API ready" : "API degraded";
	}
	return (
		<Badge className="h-7 px-3 text-xs" title={API_URL} tone={tone}>
			<Dot tone={tone} />
			{label}
		</Badge>
	);
}

function ProvisionTenantCard({ onSpawned }: { onSpawned: (run: Run) => void }) {
	const id = useId();
	const provision = useProvisionTenant();
	const [plan, setPlan] = useState<TenantPlan>("pro");

	const fieldErrors = isApiError(provision.error, "validation_failed")
		? (provision.error as ValidationResponseError).fieldErrors
		: {};

	const onSubmit = (event: FormEvent<HTMLFormElement>): void => {
		event.preventDefault();
		const form = new FormData(event.currentTarget);
		const input: ProvisionTenantInput = {
			activation_delay_seconds: Number(form.get("delay") ?? 0),
			admin_email: String(form.get("email") ?? ""),
			plan,
			tenant_id: String(form.get("tenant") ?? ""),
		};
		provision.mutate(input, {
			onError: (error) => {
				if (!isApiError(error, "validation_failed")) {
					toast.error(error.message);
				}
			},
			onSuccess: (accepted) => {
				toast.success(`Spawned ${accepted.task_name}`);
				onSpawned({
					accepted,
					plan,
					startedAt: Date.now(),
					tenantId: input.tenant_id,
				});
			},
		});
	};

	return (
		<Card>
			<CardHeader
				description="POST /api/v1/tenants returns 202 with the task to poll."
				title="Provision a tenant"
			/>
			<form className="grid gap-4 px-5 py-5" onSubmit={onSubmit}>
				<Field
					help={
						fieldErrors.tenant_id ?? "Lowercase letters, digits and dashes."
					}
					htmlFor={`${id}-tenant`}
					label="Tenant ID"
				>
					<Input
						aria-invalid={Boolean(fieldErrors.tenant_id)}
						autoComplete="off"
						defaultValue="acme-demo"
						id={`${id}-tenant`}
						name="tenant"
						required
					/>
				</Field>
				<Field
					help={fieldErrors.admin_email}
					htmlFor={`${id}-email`}
					label="Admin email"
				>
					<Input
						aria-invalid={Boolean(fieldErrors.admin_email)}
						defaultValue="ops@example.com"
						id={`${id}-email`}
						name="email"
						required
						type="email"
					/>
				</Field>
				<fieldset className="grid gap-1.5">
					<legend className="text-foreground mb-1.5 text-sm font-medium">
						Plan
					</legend>
					<div className="bg-muted grid grid-cols-3 gap-1 rounded-md p-1">
						{PLANS.map((value) => (
							<button
								aria-pressed={plan === value}
								className={cn(
									"h-7 rounded text-sm capitalize transition-colors",
									plan === value
										? "bg-background text-foreground shadow-xs"
										: "text-muted-foreground hover:text-foreground"
								)}
								key={value}
								onClick={() => setPlan(value)}
								type="button"
							>
								{value}
							</button>
						))}
					</div>
				</fieldset>
				<Field
					help={
						fieldErrors.activation_delay_seconds ??
						"Durable sleep before activation. The worker suspends and resumes."
					}
					htmlFor={`${id}-delay`}
					label="Activation delay (seconds)"
				>
					<Input
						aria-invalid={Boolean(fieldErrors.activation_delay_seconds)}
						defaultValue={3}
						id={`${id}-delay`}
						max={3600}
						min={0}
						name="delay"
						step="any"
						type="number"
					/>
				</Field>
				<Button disabled={provision.isPending} type="submit" variant="primary">
					<PlayIcon />
					{provision.isPending ? "Spawning…" : "Spawn workflow"}
				</Button>
			</form>
		</Card>
	);
}

function RunsCard({ runs, onClear }: { runs: Run[]; onClear: () => void }) {
	return (
		<Card>
			<CardHeader
				action={
					runs.length > 0 ? (
						<Button onClick={onClear} size="sm" variant="ghost">
							<Trash2Icon />
							Clear
						</Button>
					) : null
				}
				description="GET /api/v1/tasks/{task_id}, polled every second until the task settles."
				title="Recent runs"
			/>
			{runs.length === 0 ? (
				<div className="p-5">
					<EmptyState
						description="Spawn a workflow and its checkpoints show up here as the worker moves through them."
						icon={<WorkflowIcon className="size-4" />}
						title="No runs yet"
					/>
				</div>
			) : (
				<Table>
					<thead>
						<tr>
							<Th>Tenant</Th>
							<Th>State</Th>
							<Th>Result</Th>
							<Th>Started</Th>
							<Th className="text-right">
								<span className="sr-only">Actions</span>
							</Th>
						</tr>
					</thead>
					<tbody>
						{runs.map((run) => (
							<RunRow key={run.accepted.task_id} run={run} />
						))}
					</tbody>
				</Table>
			)}
			<CardFooter>
				<span>Runs are remembered in this browser only.</span>
			</CardFooter>
		</Card>
	);
}

function RunRow({ run }: { run: Run }) {
	const queue = run.accepted.queue as Queue;
	const task = useTask(run.accepted.task_id, queue);
	const cancel = useCancelTask();
	const state = task.data?.state;
	const settled = state !== undefined && TERMINAL_STATES.has(state);

	let stateCell: React.ReactNode = <Badge tone="busy">loading</Badge>;
	if (task.isError) {
		stateCell = (
			<Badge title={task.error.message} tone="error">
				{isApiError(task.error, "not_found") ? "not found" : "error"}
			</Badge>
		);
	} else if (state) {
		stateCell = (
			<Badge tone={STATE_TONES[state]}>
				<Dot tone={STATE_TONES[state]} />
				{state}
			</Badge>
		);
	}

	return (
		<Tr>
			<Td>
				<div className="grid gap-0.5">
					<span className="font-medium">{run.tenantId}</span>
					<Mono className="text-muted-foreground text-xs">
						{run.accepted.task_id.slice(0, 8)} · {run.plan}
					</Mono>
				</div>
			</Td>
			<Td>{stateCell}</Td>
			<Td className="text-muted-foreground max-w-64 truncate text-xs">
				<TaskOutcome failure={task.data?.failure} result={task.data?.result} />
			</Td>
			<Td className="text-muted-foreground text-xs whitespace-nowrap">
				{formatDistanceToNowStrict(run.startedAt, { addSuffix: true })}
			</Td>
			<Td className="text-right">
				<Button
					aria-label="Cancel task"
					disabled={settled || cancel.isPending || !state}
					onClick={() =>
						cancel.mutate(
							{ queue, taskId: run.accepted.task_id },
							{
								onError: (error) => toast.error(error.message),
								onSuccess: () => toast.success("Task cancelled"),
							}
						)
					}
					size="icon-sm"
					variant="ghost"
				>
					<SquareIcon />
				</Button>
			</Td>
		</Tr>
	);
}

/** `result`/`failure` are task-defined JSON, so they're shown, not typed. */
function TaskOutcome({
	result,
	failure,
}: {
	result: unknown;
	failure: unknown;
}) {
	if (failure !== null && failure !== undefined) {
		return <span className="text-destructive">{JSON.stringify(failure)}</span>;
	}
	if (result !== null && result !== undefined) {
		const resources =
			typeof result === "object" && "resources" in result
				? (result as { resources: unknown }).resources
				: undefined;
		return (
			<span title={JSON.stringify(result, null, 2)}>
				{Array.isArray(resources)
					? resources.join(", ")
					: JSON.stringify(result)}
			</span>
		);
	}
	return <span>—</span>;
}
