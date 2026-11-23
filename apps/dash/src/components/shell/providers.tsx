"use client";

import { Toaster } from "@securefabric/ui/components/sonner";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { useState } from "react";
import { TooltipProvider } from "@/components/ui/overlay";

export function Providers({ children }: { children: React.ReactNode }) {
	// One client per mount, not per module: a module-level client would be
	// shared across requests during server render.
	const [queryClient] = useState(() => new QueryClient());
	return (
		<ThemeProvider
			attribute="class"
			defaultTheme="system"
			disableTransitionOnChange
			enableSystem
		>
			<QueryClientProvider client={queryClient}>
				{/* URL state for the data tables (lib/store/adapters/nuqs). */}
				<NuqsAdapter>
					<TooltipProvider delay={300}>{children}</TooltipProvider>
				</NuqsAdapter>
			</QueryClientProvider>
			<Toaster position="bottom-right" />
		</ThemeProvider>
	);
}
