import {
	createElement,
	type ReactNode,
	useCallback,
	useEffect,
	useRef,
	useState,
} from "react";
import { type ConnectHandle, type ConnectOptions, connect } from "./index";

/**
 * React wrapper: `const { open, isOpen } = useSecureFabricConnect({ url, onSuccess })`.
 * Options are read when `open()` runs, so inline callbacks are fine. The flow
 * closes if the component unmounts.
 */
export function useSecureFabricConnect(options: ConnectOptions): {
	open: () => void;
	close: () => void;
	isOpen: boolean;
} {
	const latest = useRef(options);
	latest.current = options;
	const handle = useRef<ConnectHandle | null>(null);
	const [isOpen, setOpen] = useState(false);
	const open = useCallback(() => {
		handle.current?.close();
		const o = latest.current;
		handle.current = connect({
			...o,
			onClose: () => {
				setOpen(false);
				latest.current.onClose?.();
			},
			onError: (e) => latest.current.onError?.(e),
			onEvent: (e) => latest.current.onEvent?.(e),
			onSuccess: (r) => latest.current.onSuccess?.(r),
		});
		handle.current.open();
		setOpen(handle.current.isOpen);
	}, []);
	const close = useCallback(() => handle.current?.close(), []);
	useEffect(() => () => handle.current?.close(), []);
	return { close, isOpen, open };
}

/** A button that opens the flow. Style it with `className`. */
export function ConnectButton({
	children = "Connect",
	className,
	...options
}: ConnectOptions & { children?: ReactNode; className?: string }) {
	const { open, isOpen } = useSecureFabricConnect(options);
	return createElement(
		"button",
		{ className, disabled: isOpen, onClick: open, type: "button" },
		children
	);
}
