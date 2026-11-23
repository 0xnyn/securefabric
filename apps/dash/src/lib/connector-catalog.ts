/**
 * Everything the catalog shows that the API doesn't know yet: logos that work
 * in both themes, and the connectors on the roadmap.
 *
 * Live connectors come from `GET /v1/connectors` (their manifests); this file
 * only adds presentation for them. Planned connectors exist only here, from
 * the vulnerability and AppSec plan (research/vuln-appsec-reference.md):
 * tier A ships by the end of February 2027, tier B when the vendor grants
 * partner access, tier C in March–April, and detection and posture sources
 * from March. When a planned connector ships, the API lists it and the
 * catalog stops showing this entry (matched by id).
 */

export interface LogoSource {
	/** For dark mode, when the light mark is dark on transparent. */
	dark?: string;
	light: string;
}

const logo = (file: string, dark?: string): LogoSource => ({
	dark: dark ? `/integrations/${dark}` : undefined,
	light: `/integrations/${file}`,
});

/** Logos by connector id. A connector without one gets a monogram tile. */
export const CONNECTOR_LOGOS: Record<string, LogoSource> = {
	AIKIDO: logo("aikido.png"),
	ARNICA: logo("arnica.png"),
	AWS_GUARDDUTY: logo("aws.svg", "aws-dark.svg"),
	AWS_INSPECTOR2: logo("aws.svg", "aws-dark.svg"),
	AWS_SECURITY_HUB: logo("aws.svg", "aws-dark.svg"),
	CHECKMARX: logo("checkmarx.svg"),
	CROWDSTRIKE_EDR: logo("crowdstrike.png"),
	CROWDSTRIKE_SPOTLIGHT: logo("crowdstrike.png"),
	GITHUB: logo("github.svg", "github-dark.svg"),
	GITLAB: logo("gitlab.svg"),
	HEELER: logo("heeler.png"),
	INSIGHTVM: logo("rapid7.png"),
	MEND: logo("mend.png"),
	MS_DEFENDER_CLOUD: logo("microsoft-defender.svg"),
	MS_DEFENDER_ENDPOINT: logo("microsoft-defender.svg"),
	MS_DEFENDER_VMS: logo("microsoft-defender.svg"),
	MS_DEFENDER_VMS_GCC_HIGH: logo("microsoft-defender.svg"),
	MS_INTUNE: logo("entra.png"),
	ORCA: logo("orca.svg"),
	QUALYS: logo("qualys.svg"),
	SANDBOX: logo("securefabric.svg"),
	SANDBOX_CC: logo("securefabric.svg"),
	SANDBOX_OAUTH: logo("securefabric.svg"),
	SEMGREP: logo("semgrep.svg"),
	SENTINELONE_VMS: logo("sentinelone.png"),
	SNYK: logo("snyk.svg", "snyk-dark.svg"),
	SOCKET: logo("socket.svg"),
	SONARQUBE: logo("sonarqube.svg"),
	TANIUM_VMS: logo("tanium.svg"),
	TENABLE: logo("tenable.svg"),
	UPWIND: logo("upwind.png"),
	WIZ_CODE: logo("wiz.png"),
	WIZ_CSPM: logo("wiz.png"),
	WIZ_VMS: logo("wiz.png"),
};

export type CategoryId =
	| "code"
	| "vulnerability"
	| "cloud"
	| "detection"
	| "testing";

export const CATEGORIES: { id: CategoryId; label: string; blurb: string }[] = [
	{
		blurb: "Code, dependency, secret and infrastructure-as-code scanners",
		id: "code",
		label: "Application security",
	},
	{
		blurb: "Host and endpoint vulnerability scanners",
		id: "vulnerability",
		label: "Vulnerability management",
	},
	{
		blurb: "Cloud, container and Kubernetes security platforms",
		id: "cloud",
		label: "Cloud security",
	},
	{
		blurb: "Threat detections and configuration posture",
		id: "detection",
		label: "Detection and posture",
	},
	{
		blurb: "Synthetic data for building and testing without a real vendor",
		id: "testing",
		label: "Testing",
	},
];

/** Map a live connector's manifest categories onto the catalog's. */
export function categoryOf(categories: readonly string[]): CategoryId {
	const c = categories.join(" ").toLowerCase();
	if (c.includes("sandbox")) {
		return "testing";
	}
	if (c.includes("cloud") || c.includes("cnapp")) {
		return "cloud";
	}
	if (c.includes("vms") || c.includes("vulnerability_management")) {
		return "vulnerability";
	}
	if (c.includes("detection") || c.includes("edr")) {
		return "detection";
	}
	return "code";
}

export type Release =
	/** Committed for the February 2027 launch. */
	| "february"
	/** Built as soon as the vendor grants partner access. */
	| "partner"
	/** March–April 2027. */
	| "spring"
	/** Detection and posture objects, from March 2027. */
	| "detection";

export const RELEASES: Record<Release, { label: string; detail: string }> = {
	detection: {
		detail: "Arrives with the new detection and posture finding types.",
		label: "Coming March–May 2027",
	},
	february: {
		detail: "Committed for the February 2027 launch.",
		label: "Coming February 2027",
	},
	partner: {
		detail:
			"We start building once the vendor grants partner access. Tell us if you need one sooner.",
		label: "Waiting on vendor access",
	},
	spring: {
		detail: "Scheduled after the February launch.",
		label: "Coming March–April 2027",
	},
};

export interface PlannedConnector {
	/** What a customer needs to connect it, in one sentence. */
	auth: string;
	category: CategoryId;
	description: string;
	/** Finding types it will produce (the `type` field on findings). */
	findings: string[];
	id: string;
	name: string;
	release: Release;
	/** Resource types it will produce. */
	resources: string[];
	vendor: string;
}

export const PLANNED: PlannedConnector[] = [
	// Tier A: February 2027.
	{
		auth: "The SecureFabric GitHub App, installed on their organization.",
		category: "code",
		description:
			"Code scanning, secret scanning and Dependabot alerts from GitHub Advanced Security.",
		findings: ["CODE", "SECRET", "DEPENDENCY"],
		id: "GITHUB",
		name: "GitHub Advanced Security",
		release: "february",
		resources: ["REPOSITORY", "BRANCH"],
		vendor: "GitHub",
	},
	{
		auth: "An access key and secret key, ideally for a dedicated user.",
		category: "vulnerability",
		description:
			"Host vulnerabilities and assets from Tenable Vulnerability Management.",
		findings: ["HOST"],
		id: "TENABLE",
		name: "Tenable Vulnerability Management",
		release: "february",
		resources: ["HOST"],
		vendor: "Tenable",
	},
	{
		auth: "Admin consent for the SecureFabric app in their Microsoft Entra tenant.",
		category: "vulnerability",
		description:
			"Device vulnerabilities and software inventory from Microsoft Defender.",
		findings: ["HOST"],
		id: "MS_DEFENDER_VMS",
		name: "Microsoft Defender Vulnerability Management",
		release: "february",
		resources: ["HOST"],
		vendor: "Microsoft",
	},
	{
		auth: "An IAM role with read-only Inspector access and an external ID.",
		category: "cloud",
		description:
			"EC2, ECR image, Lambda and code findings from Amazon Inspector, across your AWS organization.",
		findings: ["HOST", "CONTAINER", "DEPENDENCY", "CODE", "IAC"],
		id: "AWS_INSPECTOR2",
		name: "Amazon Inspector",
		release: "february",
		resources: ["HOST", "IMAGE", "CONTAINER", "FUNCTION", "REPOSITORY"],
		vendor: "AWS",
	},
	{
		auth: "A Qualys user with API access, and their platform URL.",
		category: "vulnerability",
		description: "Host detections and assets from Qualys VMDR.",
		findings: ["HOST"],
		id: "QUALYS",
		name: "Qualys VMDR",
		release: "february",
		resources: ["HOST"],
		vendor: "Qualys",
	},
	{
		auth: "A group or project access token with the read_api scope.",
		category: "code",
		description:
			"The vulnerability report from GitLab Ultimate: SAST, dependency, container, secret and IaC findings.",
		findings: ["CODE", "DEPENDENCY", "CONTAINER", "SECRET", "IAC"],
		id: "GITLAB",
		name: "GitLab Ultimate",
		release: "february",
		resources: ["REPOSITORY", "BRANCH", "IMAGE"],
		vendor: "GitLab",
	},
	{
		auth: "A SonarQube user token.",
		category: "code",
		description:
			"Code vulnerabilities and security hotspots from SonarQube Server and SonarQube Cloud.",
		findings: ["CODE"],
		id: "SONARQUBE",
		name: "SonarQube",
		release: "february",
		resources: ["REPOSITORY", "BRANCH"],
		vendor: "SonarSource",
	},
	{
		auth: "A Semgrep web API token for their deployment.",
		category: "code",
		description: "Code, supply chain and secrets findings from Semgrep.",
		findings: ["CODE", "DEPENDENCY", "SECRET"],
		id: "SEMGREP",
		name: "Semgrep",
		release: "february",
		resources: ["REPOSITORY", "BRANCH"],
		vendor: "Semgrep",
	},
	{
		auth: "An Aikido OAuth client ID and secret.",
		category: "code",
		description:
			"Code, dependency, secret, container and IaC issues from Aikido Security.",
		findings: ["CODE", "DEPENDENCY", "SECRET", "CONTAINER", "IAC"],
		id: "AIKIDO",
		name: "Aikido Security",
		release: "february",
		resources: ["REPOSITORY", "IMAGE", "CONTAINER"],
		vendor: "Aikido",
	},
	{
		auth: "A Socket organization API token.",
		category: "code",
		description: "Supply chain risk alerts on your dependencies from Socket.",
		findings: ["DEPENDENCY"],
		id: "SOCKET",
		name: "Socket",
		release: "february",
		resources: ["REPOSITORY", "DEPENDENCY"],
		vendor: "Socket",
	},
	// Tier B: as soon as the vendor grants partner access.
	{
		auth: "A Falcon API client with Vulnerabilities and Hosts read scopes.",
		category: "vulnerability",
		description:
			"Host vulnerabilities from CrowdStrike Falcon Exposure Management (Spotlight).",
		findings: ["HOST"],
		id: "CROWDSTRIKE_SPOTLIGHT",
		name: "CrowdStrike Falcon Spotlight",
		release: "partner",
		resources: ["HOST"],
		vendor: "CrowdStrike",
	},
	{
		auth: "A Wiz service account.",
		category: "cloud",
		description:
			"Vulnerability findings on hosts, containers, images and Kubernetes from Wiz.",
		findings: ["HOST", "CONTAINER", "DEPENDENCY"],
		id: "WIZ_VMS",
		name: "Wiz",
		release: "partner",
		resources: ["HOST", "CONTAINER", "IMAGE", "KUBERNETES"],
		vendor: "Wiz",
	},
	{
		auth: "A Wiz service account with Wiz Code enabled.",
		category: "code",
		description: "Code, dependency, secret and IaC findings from Wiz Code.",
		findings: ["CODE", "DEPENDENCY", "SECRET", "IAC"],
		id: "WIZ_CODE",
		name: "Wiz Code",
		release: "partner",
		resources: ["REPOSITORY", "BRANCH"],
		vendor: "Wiz",
	},
	{
		auth: "The SecureFabric Snyk App, authorized for their Snyk organization.",
		category: "code",
		description: "Open Source, Code, Container and IaC issues from Snyk.",
		findings: ["DEPENDENCY", "CODE", "CONTAINER", "IAC"],
		id: "SNYK",
		name: "Snyk",
		release: "partner",
		resources: ["REPOSITORY", "IMAGE", "DEPENDENCY"],
		vendor: "Snyk",
	},
	{
		auth: "An Upwind OAuth client for their region.",
		category: "cloud",
		description:
			"Vulnerabilities and code risks across hosts, containers and Kubernetes from Upwind.",
		findings: ["HOST", "CONTAINER", "DEPENDENCY", "CODE", "SECRET", "IAC"],
		id: "UPWIND",
		name: "Upwind",
		release: "partner",
		resources: ["HOST", "CONTAINER", "IMAGE", "KUBERNETES", "REPOSITORY"],
		vendor: "Upwind",
	},
	{
		auth: "A Tanium API token with Asset and Comply read access.",
		category: "vulnerability",
		description: "Endpoint vulnerability findings from Tanium Comply.",
		findings: ["HOST"],
		id: "TANIUM_VMS",
		name: "Tanium Comply",
		release: "partner",
		resources: ["HOST"],
		vendor: "Tanium",
	},
	// Tier C: March–April 2027.
	{
		auth: "An Insight Platform API key for their region.",
		category: "vulnerability",
		description: "Asset vulnerabilities from Rapid7 InsightVM.",
		findings: ["HOST"],
		id: "INSIGHTVM",
		name: "Rapid7 InsightVM",
		release: "spring",
		resources: ["HOST"],
		vendor: "Rapid7",
	},
	{
		auth: "A service user token with view access to risks.",
		category: "vulnerability",
		description:
			"Endpoint vulnerabilities from SentinelOne Singularity Vulnerability Management.",
		findings: ["HOST"],
		id: "SENTINELONE_VMS",
		name: "SentinelOne Vulnerability Management",
		release: "spring",
		resources: ["HOST"],
		vendor: "SentinelOne",
	},
	{
		auth: "An app registration in their Azure Government tenant.",
		category: "vulnerability",
		description:
			"Microsoft Defender Vulnerability Management for GCC High tenants.",
		findings: ["HOST"],
		id: "MS_DEFENDER_VMS_GCC_HIGH",
		name: "Microsoft Defender (GCC High)",
		release: "spring",
		resources: ["HOST"],
		vendor: "Microsoft",
	},
	{
		auth: "A Mend user key and organization ID.",
		category: "code",
		description: "Dependency, code and container findings from Mend.",
		findings: ["DEPENDENCY", "CODE", "CONTAINER"],
		id: "MEND",
		name: "Mend",
		release: "spring",
		resources: ["REPOSITORY", "IMAGE", "DEPENDENCY"],
		vendor: "Mend.io",
	},
	{
		auth: "An Orca API token with the Viewer role.",
		category: "cloud",
		description:
			"Vulnerabilities on cloud hosts, containers and images from Orca Security.",
		findings: ["HOST", "CONTAINER", "DEPENDENCY"],
		id: "ORCA",
		name: "Orca Security",
		release: "spring",
		resources: ["HOST", "CONTAINER", "IMAGE"],
		vendor: "Orca",
	},
	{
		auth: "A Checkmarx One OAuth client for their tenant.",
		category: "code",
		description: "SAST, SCA, IaC and container findings from Checkmarx One.",
		findings: ["CODE", "DEPENDENCY", "IAC", "CONTAINER"],
		id: "CHECKMARX",
		name: "Checkmarx One",
		release: "spring",
		resources: ["REPOSITORY", "BRANCH", "IMAGE"],
		vendor: "Checkmarx",
	},
	{
		auth: "A Black Duck API token.",
		category: "code",
		description:
			"Open source vulnerabilities in your project versions from Black Duck SCA.",
		findings: ["DEPENDENCY"],
		id: "BLACK_DUCK_SCA",
		name: "Black Duck SCA",
		release: "spring",
		resources: ["REPOSITORY", "DEPENDENCY"],
		vendor: "Black Duck",
	},
	{
		auth: "A Coverity Connect user with the Observer role.",
		category: "code",
		description: "Static analysis defects from Black Duck Coverity.",
		findings: ["CODE"],
		id: "BLACK_DUCK_COVERITY",
		name: "Black Duck Coverity",
		release: "spring",
		resources: ["REPOSITORY"],
		vendor: "Black Duck",
	},
	{
		auth: "An Arnica API token.",
		category: "code",
		description: "Code, secret and dependency risks from Arnica.",
		findings: ["CODE", "SECRET", "DEPENDENCY"],
		id: "ARNICA",
		name: "Arnica",
		release: "spring",
		resources: ["REPOSITORY"],
		vendor: "Arnica",
	},
	{
		auth: "A Heeler API token.",
		category: "code",
		description: "Dependency and secret risks from Heeler.",
		findings: ["DEPENDENCY", "SECRET"],
		id: "HEELER",
		name: "Heeler",
		release: "spring",
		resources: ["REPOSITORY", "DEPENDENCY"],
		vendor: "Heeler",
	},
	// Detection and posture: from March 2027.
	{
		auth: "A Falcon API client with Detections read access.",
		category: "detection",
		description: "Endpoint detections from CrowdStrike Falcon Insight.",
		findings: [],
		id: "CROWDSTRIKE_EDR",
		name: "CrowdStrike Falcon Insight",
		release: "detection",
		resources: ["HOST"],
		vendor: "CrowdStrike",
	},
	{
		auth: "Admin consent for the SecureFabric app in their Microsoft Entra tenant.",
		category: "detection",
		description:
			"Alerts and device inventory from Microsoft Defender for Endpoint.",
		findings: [],
		id: "MS_DEFENDER_ENDPOINT",
		name: "Microsoft Defender for Endpoint",
		release: "detection",
		resources: ["HOST"],
		vendor: "Microsoft",
	},
	{
		auth: "An IAM role with read-only GuardDuty access.",
		category: "detection",
		description: "Threat detections from Amazon GuardDuty.",
		findings: [],
		id: "AWS_GUARDDUTY",
		name: "Amazon GuardDuty",
		release: "detection",
		resources: ["HOST"],
		vendor: "AWS",
	},
	{
		auth: "An IAM role with read-only Security Hub access.",
		category: "detection",
		description:
			"Misconfigurations and aggregated findings from AWS Security Hub.",
		findings: [],
		id: "AWS_SECURITY_HUB",
		name: "AWS Security Hub",
		release: "detection",
		resources: ["HOST"],
		vendor: "AWS",
	},
	{
		auth: "Reader access to their Azure subscriptions.",
		category: "detection",
		description:
			"Security recommendations and alerts from Microsoft Defender for Cloud.",
		findings: [],
		id: "MS_DEFENDER_CLOUD",
		name: "Microsoft Defender for Cloud",
		release: "detection",
		resources: ["HOST"],
		vendor: "Microsoft",
	},
	{
		auth: "Admin consent for the SecureFabric app in their Microsoft Entra tenant.",
		category: "detection",
		description:
			"Managed devices and their compliance state from Microsoft Intune.",
		findings: [],
		id: "MS_INTUNE",
		name: "Microsoft Intune",
		release: "detection",
		resources: ["HOST"],
		vendor: "Microsoft",
	},
	{
		auth: "A Wiz service account.",
		category: "detection",
		description: "Cloud configuration findings from Wiz.",
		findings: [],
		id: "WIZ_CSPM",
		name: "Wiz Cloud",
		release: "detection",
		resources: ["HOST", "KUBERNETES"],
		vendor: "Wiz",
	},
];

/** Readable names for the resource and finding type enums. */
export const TYPE_LABELS: Record<string, string> = {
	BRANCH: "Branches",
	CODE: "Code",
	CONTAINER: "Containers",
	DEPENDENCY: "Dependencies",
	DOMAIN: "Domains",
	FUNCTION: "Functions",
	HOST: "Hosts",
	IAC: "Infrastructure as code",
	IMAGE: "Images",
	KUBERNETES: "Kubernetes",
	REPOSITORY: "Repositories",
	SECRET: "Secrets",
	SOFTWARE: "Software",
	VENDOR: "Vendors",
};

export function typeLabel(value: string): string {
	return (
		TYPE_LABELS[value] ??
		value.charAt(0) + value.slice(1).toLowerCase().replaceAll("_", " ")
	);
}

/** How a connection authenticates, in words (schema AuthMode). */
export const AUTH_LABELS: Record<string, string> = {
	API_KEY: "API key",
	APP: "App installation",
	AWS_ROLE: "AWS IAM role",
	BASIC: "Username and password",
	OAUTH2: "OAuth sign-in",
	OAUTH2_CC: "OAuth client credentials",
};

export function authLabel(mode: string): string {
	return AUTH_LABELS[mode] ?? mode;
}

/** What the customer does on the connect page (schema ConnectStyle). */
export function connectSentence(connect: string, vendor: string): string {
	return connect === "redirect"
		? `Signs in to ${vendor} and approves read-only access.`
		: `Pastes ${vendor} credentials into the connect page.`;
}

/** How a stream picks up changes (schema SyncMode). */
export const SYNC_MODE_LABELS: Record<string, string> = {
	export: "Bulk export each run",
	full: "Full read each run",
	incremental: "Changes since the last run",
};

/** How a stream learns that a record is gone (schema DeletionMode). */
export const DELETION_LABELS: Record<string, string> = {
	none: "Records are never removed",
	sweep: "Removed when a full read no longer sees them",
	vendor_reported: "Removed when the vendor reports it",
};

/** "every hour", "every 15 minutes", "every day" from seconds. */
export function everySeconds(seconds: number): string {
	if (seconds % 86_400 === 0) {
		const d = seconds / 86_400;
		return d === 1 ? "every day" : `every ${d} days`;
	}
	if (seconds % 3600 === 0) {
		const h = seconds / 3600;
		return h === 1 ? "every hour" : `every ${h} hours`;
	}
	const m = Math.round(seconds / 60);
	return m === 1 ? "every minute" : `every ${m} minutes`;
}
