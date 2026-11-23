import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../lib/utils";

/** Vercel-style buttons: rounded-md on a 28/32/36/40px scale shared with
 * inputs and selects, a monochrome primary in dark mode and the brand indigo
 * in light.
 *
 * The variant and size names are a superset of shadcn's, so the generated
 * primitives (sidebar, dialog, calendar, the data table) render with the
 * playground's buttons rather than a second set. `default` is shadcn's name
 * for the filled button; the playground calls it `primary`. Without a
 * variant a button is `secondary`, the bordered one, because a filled button
 * is reserved for the one primary action on a page. */
export const buttonVariants = cva(
	"focus-visible:ring-ring/40 inline-flex shrink-0 items-center justify-center gap-1.5 rounded-md border text-sm font-medium whitespace-nowrap transition-colors outline-none select-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
	{
		defaultVariants: { size: "md", variant: "secondary" },
		variants: {
			size: {
				// One height scale for every control: buttons, inputs and selects
				// line up in a toolbar row. md (36px) matches <Input> and the
				// default <Select>; sm (32px) matches <Select size="sm">.
				default: "h-9 px-4",
				icon: "size-9",
				"icon-lg": "size-10",
				"icon-sm": "size-8",
				"icon-xs": "size-7 [&_svg:not([class*='size-'])]:size-3.5",
				lg: "h-10 px-5",
				md: "h-9 px-4",
				sm: "h-8 px-3",
				xs: "h-7 gap-1 px-2.5 text-xs [&_svg:not([class*='size-'])]:size-3.5",
			},
			variant: {
				default:
					"bg-primary text-primary-foreground hover:bg-ds-primary-mid border-transparent",
				destructive:
					"bg-destructive text-ds-bg hover:bg-destructive/90 border-transparent",
				ghost:
					"text-muted-foreground hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground border-transparent",
				link: "text-ds-accent border-transparent underline-offset-4 hover:underline",
				outline:
					"border-border hover:bg-muted aria-expanded:bg-muted bg-transparent",
				primary:
					"bg-primary text-primary-foreground hover:bg-ds-primary-mid border-transparent",
				secondary:
					"border-border bg-background hover:bg-muted aria-expanded:bg-muted",
			},
		},
	}
);

export type ButtonProps = ButtonPrimitive.Props &
	VariantProps<typeof buttonVariants>;

/** Whether `render` still produces a native `<button>` (Base UI needs to know:
 * a link styled as a button must not get button semantics). */
function rendersNativeButton(render: ButtonProps["render"]): boolean {
	if (render === undefined) {
		return true;
	}
	return (
		typeof render === "object" &&
		render !== null &&
		"type" in render &&
		render.type === "button"
	);
}

export function Button({
	className,
	size,
	variant,
	nativeButton,
	...props
}: ButtonProps) {
	return (
		<ButtonPrimitive
			className={cn(buttonVariants({ size, variant }), className)}
			data-slot="button"
			nativeButton={nativeButton ?? rendersNativeButton(props.render)}
			{...props}
		/>
	);
}
