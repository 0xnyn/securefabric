"use client";

import { TooltipProvider } from "@securefabric/ui/components/tooltip";
import { Toaster } from "@securefabric/ui/primitives/sonner";
import {
	MutationCache,
	QueryCache,
	QueryClient,
	QueryClientProvider,
} from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { useState } from "react";
import { redirectToSignIn, retryUnlessAuth } from "@/lib/auth";

export function Providers({ children }: { children: React.ReactNode }) {
	// One client per mount, not per module: a module-level client would be
	// shared across requests during server render.
	const [queryClient] = useState(
		() =>
			new QueryClient({
				defaultOptions: { queries: { retry: retryUnlessAuth } },
				// A session that is gone (expired, signed out elsewhere) sends you
				// to sign-in instead of leaving every view failing with 401.
				mutationCache: new MutationCache({ onError: redirectToSignIn }),
				queryCache: new QueryCache({ onError: redirectToSignIn }),
			})
	);
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
