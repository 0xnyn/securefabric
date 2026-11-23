import { EnvShell } from "@/components/shell/shell";

export default function EnvLayout({ children }: { children: React.ReactNode }) {
	return <EnvShell>{children}</EnvShell>;
}
