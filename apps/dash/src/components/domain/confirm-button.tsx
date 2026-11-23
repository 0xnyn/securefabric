"use client";

import { Button } from "@securefabric/ui/components/button";
import { Dialog, DialogContent } from "@securefabric/ui/components/dialog";
import { useState } from "react";

/** A button that asks before doing something it can't undo. */
export function ConfirmButton({
	title,
	description,
	confirmLabel,
	onConfirm,
	disabled,
	children,
	size = "sm",
	variant = "destructive",
}: {
	title: string;
	description: React.ReactNode;
	confirmLabel: string;
	onConfirm: () => void;
	disabled?: boolean;
	children: React.ReactNode;
	size?: "xs" | "sm";
	variant?: "destructive" | "ghost";
}) {
	const [open, setOpen] = useState(false);
	return (
		<>
			<Button
				disabled={disabled}
				onClick={() => setOpen(true)}
				size={size}
				variant={variant}
			>
				{children}
			</Button>
			<Dialog onOpenChange={setOpen} open={open}>
				<DialogContent
					description={description}
					footer={
						<>
							<Button onClick={() => setOpen(false)}>Cancel</Button>
							<Button
								onClick={() => {
									setOpen(false);
									onConfirm();
								}}
								variant="destructive"
							>
								{confirmLabel}
							</Button>
						</>
					}
					title={title}
				>
					{null}
				</DialogContent>
			</Dialog>
		</>
	);
}
