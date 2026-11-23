import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { useState } from "react";
import { Button } from "./button";
import { Dialog, DialogContent, SheetContent } from "./dialog";

const meta = {
	args: { children: null, onOpenChange: () => undefined, open: false },
	component: Dialog,
	title: "Components/Dialog",
} satisfies Meta<typeof Dialog>;

export default meta;
type Story = StoryObj<typeof meta>;

/** Confirmations: a question naming the thing, the consequence, and the verb again. */
export const Confirm: Story = {
	render: () => {
		const [open, setOpen] = useState(false);
		return (
			<>
				<Button onClick={() => setOpen(true)} variant="destructive">
					Revoke key
				</Button>
				<Dialog onOpenChange={setOpen} open={open}>
					<DialogContent
						description="Requests with this key fail within a minute. You can't undo this."
						footer={
							<>
								<Button onClick={() => setOpen(false)}>Cancel</Button>
								<Button onClick={() => setOpen(false)} variant="destructive">
									Revoke key
								</Button>
							</>
						}
						title="Revoke “CI key”?"
					>
						{null}
					</DialogContent>
				</Dialog>
			</>
		);
	},
};

export const Sheet: Story = {
	render: () => {
		const [open, setOpen] = useState(false);
		return (
			<>
				<Button onClick={() => setOpen(true)}>Open details</Button>
				<Dialog onOpenChange={setOpen} open={open}>
					<SheetContent
						description="01a20a1d-5d54-739e"
						title="Sync: Vulnerability findings"
					>
						<div className="p-6 text-sm">Details go here.</div>
					</SheetContent>
				</Dialog>
			</>
		);
	},
};
