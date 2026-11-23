"use client";

import { Field, Input } from "@securefabric/ui/components/form";
import { Select } from "@securefabric/ui/components/select";
import { Switch } from "@securefabric/ui/components/switch";
import { useId } from "react";

/**
 * A form rendered from a connector's JSON Schema and nothing else (CAT-04):
 * titles, descriptions, patterns, defaults, enums, `x-secret` (password
 * inputs), `x-order`, `readOnly` (hidden) and `required`. No connector-specific
 * UI code exists anywhere in the dashboard.
 */
export interface JsonSchema {
	description?: string;
	properties?: Record<string, JsonSchemaProperty>;
	required?: string[];
	title?: string;
	type?: string;
}

export interface JsonSchemaProperty {
	default?: unknown;
	description?: string;
	enum?: unknown[];
	maximum?: number;
	minimum?: number;
	pattern?: string;
	readOnly?: boolean;
	secret?: boolean;
	title?: string;
	type?: string | string[];
	"x-order"?: number;
	"x-secret"?: boolean;
}

export type FormValues = Record<string, unknown>;

const FIRST_LETTER = /^\w/u;
const ACRONYM_START = /^[A-Z]{2}/u;

/** "Tenant ID" → "tenant ID": lower-case the first letter unless it starts an acronym. */
function lower(text: string): string {
	return ACRONYM_START.test(text)
		? text
		: text.charAt(0).toLowerCase() + text.slice(1);
}

function label(name: string, prop: JsonSchemaProperty): string {
	return (
		prop.title ??
		name.replaceAll("_", " ").replace(FIRST_LETTER, (c) => c.toUpperCase())
	);
}

/** Fields in render order: `x-order` first, then declaration order. Read-only fields are not inputs. */
export function orderedFields(
	schema: JsonSchema | null | undefined
): [string, JsonSchemaProperty][] {
	const entries = Object.entries(schema?.properties ?? {}).filter(
		([, p]) => !p.readOnly
	);
	return entries
		.map((e, i) => ({ e, i }))
		.sort(
			(a, b) =>
				(a.e[1]["x-order"] ?? 1000 + a.i) - (b.e[1]["x-order"] ?? 1000 + b.i)
		)
		.map(({ e }) => e);
}

/** Initial values from `default`s. */
export function defaultsFor(
	schema: JsonSchema | null | undefined,
	presets: FormValues = {}
): FormValues {
	const out: FormValues = {};
	for (const [name, prop] of orderedFields(schema)) {
		if (prop.default !== undefined) {
			out[name] = prop.default;
		}
	}
	return { ...out, ...presets };
}

function isType(prop: JsonSchemaProperty, t: string): boolean {
	return Array.isArray(prop.type) ? prop.type.includes(t) : prop.type === t;
}

function isNumeric(prop: JsonSchemaProperty): boolean {
	return isType(prop, "integer") || isType(prop, "number");
}

/** A pattern the browser can't compile is left to the API to enforce. */
function matches(pattern: string, value: string): boolean {
	try {
		return new RegExp(pattern, "u").test(value);
	} catch {
		return true;
	}
}

function rangeError(prop: JsonSchemaProperty, v: number): string | null {
	if (prop.minimum !== undefined && v < prop.minimum) {
		return `Enter ${prop.minimum} or more`;
	}
	if (prop.maximum !== undefined && v > prop.maximum) {
		return `Enter ${prop.maximum} or less`;
	}
	return null;
}

function fieldError(
	name: string,
	prop: JsonSchemaProperty,
	v: unknown,
	required: boolean
): string | null {
	if (v === undefined || v === null || v === "") {
		return required ? `Enter the ${lower(label(name, prop))}` : null;
	}
	if (prop.pattern && typeof v === "string" && !matches(prop.pattern, v)) {
		return `This doesn't look like a valid ${lower(label(name, prop))}. Check for missing characters or extra spaces.`;
	}
	if (isNumeric(prop) && typeof v === "number") {
		return rangeError(prop, v);
	}
	return null;
}

/** Client-side checks the schema states (the API validates again). Returns field → message. */
export function validate(
	schema: JsonSchema | null | undefined,
	values: FormValues
): Record<string, string> {
	const errors: Record<string, string> = {};
	const required = new Set(schema?.required ?? []);
	for (const [name, prop] of orderedFields(schema)) {
		const message = fieldError(name, prop, values[name], required.has(name));
		if (message) {
			errors[name] = message;
		}
	}
	return errors;
}

function inputType(prop: JsonSchemaProperty): "password" | "number" | "text" {
	if (prop["x-secret"] || prop.secret) {
		return "password";
	}
	return isNumeric(prop) ? "number" : "text";
}

function SchemaField({
	id,
	name,
	prop,
	required,
	value,
	error,
	onChange,
}: {
	id: string;
	name: string;
	prop: JsonSchemaProperty;
	required: boolean;
	value: unknown;
	error?: string;
	onChange: (value: unknown) => void;
}) {
	const help = error ? (
		<span className="text-destructive" role="alert">
			{error}
		</span>
	) : (
		prop.description
	);
	const title = `${label(name, prop)}${required ? "" : " (optional)"}`;
	if (prop.enum) {
		return (
			<Field help={help} htmlFor={id} label={title}>
				<Select
					ariaLabel={label(name, prop)}
					onChange={onChange}
					options={prop.enum.map((v) => ({
						label: String(v),
						value: String(v),
					}))}
					value={String(value ?? prop.default ?? "")}
				/>
			</Field>
		);
	}
	if (isType(prop, "boolean")) {
		return (
			<div className="flex items-start justify-between gap-4">
				<div className="grid gap-0.5">
					<span className="text-sm font-medium">{label(name, prop)}</span>
					{help ? (
						<span className="text-muted-foreground text-xs">{help}</span>
					) : null}
				</div>
				<Switch
					ariaLabel={label(name, prop)}
					checked={Boolean(value ?? prop.default)}
					id={id}
					onChange={onChange}
				/>
			</div>
		);
	}
	const type = inputType(prop);
	return (
		<Field help={help} htmlFor={id} label={title}>
			<Input
				aria-invalid={error ? true : undefined}
				autoComplete={type === "password" ? "off" : undefined}
				className={type === "password" ? "font-mono" : undefined}
				id={id}
				max={prop.maximum}
				min={prop.minimum}
				onChange={(e) => {
					const raw = e.target.value;
					if (type === "number") {
						onChange(raw === "" ? undefined : Number(raw));
					} else {
						onChange(raw);
					}
				}}
				type={type}
				value={value === undefined || value === null ? "" : String(value)}
			/>
		</Field>
	);
}

export function SchemaForm({
	schema,
	values,
	onChange,
	errors = {},
	idPrefix,
}: {
	schema: JsonSchema | null | undefined;
	values: FormValues;
	onChange: (values: FormValues) => void;
	errors?: Record<string, string>;
	idPrefix?: string;
}) {
	const auto = useId();
	const prefix = idPrefix ?? auto;
	const fields = orderedFields(schema);
	if (fields.length === 0) {
		return null;
	}
	const required = new Set(schema?.required ?? []);
	return (
		<div className="grid gap-4">
			{fields.map(([name, prop]) => (
				<SchemaField
					error={errors[name]}
					id={`${prefix}-${name}`}
					key={name}
					name={name}
					onChange={(v) => onChange({ ...values, [name]: v })}
					prop={prop}
					required={required.has(name)}
					value={values[name]}
				/>
			))}
		</div>
	);
}

/** Values without empty strings or undefined, ready to send. */
export function compactValues(values: FormValues): FormValues {
	return Object.fromEntries(
		Object.entries(values).filter(([, v]) => v !== undefined && v !== "")
	);
}
