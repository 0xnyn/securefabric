/** The provider catalogue: every security tool SecureFabric can connect to, the
 * unified models each one feeds, and the credentials a customer enters to
 * connect it. Logos live in public/integrations (copied from apps/home). */

export type CategoryKey =
	| "vulnerability"
	| "appsec"
	| "cloud"
	| "container"
	| "endpoint"
	| "identity"
	| "mdm"
	| "siem"
	| "email"
	| "network"
	| "threat-intel"
	| "ticketing"
	| "notifications"
	| "grc"
	| "tprm"
	| "asset"
	| "data"
	| "bug-bounty";

export const CATEGORIES: Record<CategoryKey, string> = {
	appsec: "Application security",
	asset: "Asset management",
	"bug-bounty": "Bug bounty",
	cloud: "Cloud security",
	container: "Container security",
	data: "Data & storage",
	email: "Email security",
	endpoint: "Endpoint & EDR",
	grc: "GRC & compliance",
	identity: "Identity & access",
	mdm: "Device management",
	network: "Network & firewall",
	notifications: "Notifications",
	siem: "SIEM & logging",
	"threat-intel": "Threat intelligence",
	ticketing: "Ticketing & ITSM",
	tprm: "Third-party risk",
	vulnerability: "Vulnerability management",
};

export const CATEGORY_ORDER: CategoryKey[] = [
	"vulnerability",
	"endpoint",
	"cloud",
	"appsec",
	"identity",
	"siem",
	"ticketing",
	"container",
	"mdm",
	"email",
	"network",
	"threat-intel",
	"grc",
	"tprm",
	"asset",
	"data",
	"notifications",
	"bug-bounty",
];

export type ModelKey =
	| "vulnerabilities"
	| "devices"
	| "detections"
	| "cloud-findings"
	| "cloud-resources"
	| "users"
	| "groups"
	| "code-findings"
	| "repositories"
	| "alerts"
	| "tickets"
	| "vendors"
	| "controls"
	| "email-threats"
	| "indicators";

export interface ModelInfo {
	description: string;
	key: ModelKey;
	name: string;
	/** Scope a customer grants in SecureFabric Connect to read this model. */
	scope: string;
}

export const MODELS: Record<ModelKey, ModelInfo> = {
	alerts: {
		description: "Security alerts and the log events behind them.",
		key: "alerts",
		name: "Alert",
		scope: "alerts:read",
	},
	"cloud-findings": {
		description:
			"Posture and configuration findings, mapped to compliance frameworks.",
		key: "cloud-findings",
		name: "CloudFinding",
		scope: "cloud:read",
	},
	"cloud-resources": {
		description:
			"Every account, bucket, instance and role, with region, tags and exposure.",
		key: "cloud-resources",
		name: "CloudResource",
		scope: "cloud:read",
	},
	"code-findings": {
		description: "SAST, SCA, secrets and IaC findings tied to a repository.",
		key: "code-findings",
		name: "CodeFinding",
		scope: "code:read",
	},
	controls: {
		description:
			"Compliance controls, their status and the evidence behind them.",
		key: "controls",
		name: "Control",
		scope: "grc:read",
	},
	detections: {
		description:
			"EDR detections with severity, verdict, process tree and MITRE ATT&CK mapping.",
		key: "detections",
		name: "Detection",
		scope: "detections:read",
	},
	devices: {
		description:
			"Endpoints and hosts, with OS, IPs, agent health and last user.",
		key: "devices",
		name: "Device",
		scope: "devices:read",
	},
	"email-threats": {
		description:
			"Phishing, BEC and malicious-link messages, with the sender's history.",
		key: "email-threats",
		name: "EmailThreat",
		scope: "email:read",
	},
	groups: {
		description: "Groups and their members across identity providers.",
		key: "groups",
		name: "Group",
		scope: "identities:read",
	},
	indicators: {
		description: "IPs, domains and hashes with reputation and actor context.",
		key: "indicators",
		name: "Indicator",
		scope: "intel:read",
	},
	repositories: {
		description: "Repositories, default branches, visibility and owners.",
		key: "repositories",
		name: "Repository",
		scope: "code:read",
	},
	tickets: {
		description: "Tickets and incidents, created and updated through the API.",
		key: "tickets",
		name: "Ticket",
		scope: "tickets:read",
	},
	users: {
		description:
			"People and service accounts, with MFA, admin status and last login.",
		key: "users",
		name: "User",
		scope: "identities:read",
	},
	vendors: {
		description: "Third parties with their security rating and open findings.",
		key: "vendors",
		name: "Vendor",
		scope: "tprm:read",
	},
	vulnerabilities: {
		description:
			"Scanner findings normalized to one severity scale, deduplicated per asset.",
		key: "vulnerabilities",
		name: "Vulnerability",
		scope: "vulnerabilities:read",
	},
};

export type AuthType =
	| "API_KEY"
	| "CLIENT_CREDENTIALS"
	| "OAUTH2"
	| "BASIC"
	| "AWS_ROLE"
	| "APP";

export const AUTH_LABELS: Record<AuthType, string> = {
	API_KEY: "API key",
	APP: "App installation",
	AWS_ROLE: "IAM role",
	BASIC: "Username & password",
	CLIENT_CREDENTIALS: "OAuth client credentials",
	OAUTH2: "OAuth 2.0",
};

export interface CredentialField {
	help?: string;
	key: string;
	label: string;
	options?: { label: string; value: string }[];
	placeholder?: string;
	secret?: boolean;
}

export type ProviderStatus = "ga" | "beta" | "soon";

export interface WriteAction {
	endpoint: string;
	name: string;
	scope: string;
}

export interface Provider {
	auth: AuthType;
	categories: CategoryKey[];
	description: string;
	fields: CredentialField[];
	logo?: string;
	models: ModelKey[];
	name: string;
	/** What the customer must set up on their side before connecting. */
	permissions: string[];
	/** Upstream product names, for the detail page. */
	products: string[];
	/** Rate limit SecureFabric stays under, as the vendor documents it. */
	rateLimit: string;
	slug: string;
	status: ProviderStatus;
	vendorDocs: string;
	writeActions: WriteAction[];
}

const CLIENT_ID: CredentialField = {
	key: "client_id",
	label: "Client ID",
	placeholder: "3f9c2a71e0b84d...",
};
const CLIENT_SECRET: CredentialField = {
	key: "client_secret",
	label: "Client secret",
	placeholder: "••••••••••••••••",
	secret: true,
};
const API_TOKEN: CredentialField = {
	key: "api_token",
	label: "API token",
	placeholder: "••••••••••••••••",
	secret: true,
};
const TENANT_ID: CredentialField = {
	help: "Directory (tenant) ID from the app registration's overview page.",
	key: "tenant_id",
	label: "Tenant ID",
	placeholder: "72f988bf-86f1-41af-91ab-2d7cd011db47",
};

function baseUrl(
	placeholder: string,
	help = "The URL you sign in to, without a trailing slash."
): CredentialField {
	return { help, key: "base_url", label: "Base URL", placeholder };
}

function regionSelect(options: [string, string][]): CredentialField {
	return {
		help: "Where your tenant is hosted. SecureFabric calls only this region.",
		key: "base_url",
		label: "Region",
		options: options.map(([label, value]) => ({ label, value })),
	};
}

const NO_WRITES: WriteAction[] = [];

const ISOLATE: WriteAction = {
	endpoint: "POST /v1/devices/{id}/isolate",
	name: "Isolate device",
	scope: "devices:isolate",
};
const CREATE_TICKET: WriteAction = {
	endpoint: "POST /v1/tickets",
	name: "Create ticket",
	scope: "tickets:write",
};
const UPDATE_TICKET: WriteAction = {
	endpoint: "PATCH /v1/tickets/{id}",
	name: "Update ticket",
	scope: "tickets:write",
};
const SUSPEND_USER: WriteAction = {
	endpoint: "POST /v1/users/{id}/suspend",
	name: "Suspend user",
	scope: "identities:write",
};
const RESOLVE_DETECTION: WriteAction = {
	endpoint: "PATCH /v1/detections/{id}",
	name: "Update detection status",
	scope: "detections:write",
};
const ACCEPT_RISK: WriteAction = {
	endpoint: "PATCH /v1/vulnerabilities/{id}",
	name: "Accept risk / change state",
	scope: "vulnerabilities:write",
};

/** Providers with full docs, sandbox data and unified models. */
const LIVE: Provider[] = [
	{
		auth: "API_KEY",
		categories: ["vulnerability"],
		description:
			"Vulnerabilities, assets and scans from Tenable Vulnerability Management and Tenable One, read through the export API so large estates sync without hitting rate limits.",
		fields: [
			{
				help: "Settings → My account → API keys in Tenable Vulnerability Management.",
				key: "access_key",
				label: "Access key",
				placeholder: "a8f0c3e9d1b74f2c...",
			},
			{
				key: "secret_key",
				label: "Secret key",
				placeholder: "••••••••••••••••",
				secret: true,
			},
		],
		logo: "tenable.svg",
		models: ["vulnerabilities", "devices"],
		name: "Tenable",
		permissions: [
			"A user with the Basic role or higher and Can View on the target groups",
			"API access enabled for that user",
		],
		products: ["Tenable Vulnerability Management", "Tenable One", "Nessus"],
		rateLimit: "Export API: 3 concurrent export jobs per container",
		slug: "tenable",
		status: "ga",
		vendorDocs: "https://developer.tenable.com",
		writeActions: [ACCEPT_RISK],
	},
	{
		auth: "BASIC",
		categories: ["vulnerability"],
		description:
			"Host and container detections by QID, asset inventory and tags from Qualys VMDR, across every Qualys platform region.",
		fields: [
			{ key: "username", label: "Username", placeholder: "acme_ap3" },
			{
				key: "password",
				label: "Password",
				placeholder: "••••••••••••",
				secret: true,
			},
			regionSelect([
				["US Platform 1", "https://qualysapi.qualys.com"],
				["US Platform 2", "https://qualysapi.qg2.apps.qualys.com"],
				["US Platform 3", "https://qualysapi.qg3.apps.qualys.com"],
				["EU Platform 1", "https://qualysapi.qualys.eu"],
				["EU Platform 2", "https://qualysapi.qg2.apps.qualys.eu"],
				["India Platform", "https://qualysapi.qg1.apps.qualys.in"],
			]),
		],
		logo: "qualys.svg",
		models: ["vulnerabilities", "devices"],
		name: "Qualys",
		permissions: [
			"A Reader user with API access in the subscription",
			"VMDR module enabled; Cloud Agent for host inventory",
		],
		products: ["VMDR", "Cloud Agent", "Container Security"],
		rateLimit: "300 calls per hour per subscription (default)",
		slug: "qualys",
		status: "ga",
		vendorDocs: "https://www.qualys.com/docs/qualys-api-vmpc-user-guide.pdf",
		writeActions: NO_WRITES,
	},
	{
		auth: "CLIENT_CREDENTIALS",
		categories: ["endpoint", "vulnerability", "cloud"],
		description:
			"Falcon devices and sensor health, detections with MITRE ATT&CK mapping, and Spotlight vulnerabilities in the same Vulnerability model as every scanner.",
		fields: [
			CLIENT_ID,
			CLIENT_SECRET,
			regionSelect([
				["US-1", "https://api.crowdstrike.com"],
				["US-2", "https://api.us-2.crowdstrike.com"],
				["EU-1", "https://api.eu-1.crowdstrike.com"],
				["US-GOV-1", "https://api.laggar.gcw.crowdstrike.com"],
			]),
		],
		logo: "crowdstrike.png",
		models: ["devices", "detections", "vulnerabilities"],
		name: "CrowdStrike Falcon",
		permissions: [
			"API client with Hosts: Read, Alerts: Read, Vulnerabilities: Read",
			"Hosts: Write for device isolation (optional)",
		],
		products: ["Falcon Insight XDR", "Falcon Spotlight", "Falcon Discover"],
		rateLimit: "6,000 requests per minute per CID",
		slug: "crowdstrike",
		status: "ga",
		vendorDocs: "https://falcon.crowdstrike.com/documentation",
		writeActions: [ISOLATE, RESOLVE_DETECTION],
	},
	{
		auth: "CLIENT_CREDENTIALS",
		categories: ["cloud", "vulnerability", "container"],
		description:
			"Cloud resources across AWS, Azure, GCP and OCI, Wiz issues as CloudFindings with the frameworks they map to, and workload vulnerabilities.",
		fields: [
			baseUrl(
				"https://api.us17.app.wiz.io",
				"Tenant info → API Endpoint URL in the Wiz portal."
			),
			CLIENT_ID,
			CLIENT_SECRET,
		],
		logo: "wiz.png",
		models: ["cloud-resources", "cloud-findings", "vulnerabilities"],
		name: "Wiz",
		permissions: [
			"Service account of type Custom Integration (GraphQL API)",
			"Scopes: read:issues, read:vulnerabilities, read:cloud_resources",
		],
		products: ["Wiz Cloud", "Wiz Code", "Wiz Defend"],
		rateLimit: "10,000 requests per hour per service account",
		slug: "wiz",
		status: "ga",
		vendorDocs: "https://win.wiz.io/reference",
		writeActions: NO_WRITES,
	},
	{
		auth: "API_KEY",
		categories: ["appsec"],
		description:
			"Open source, container, IaC and code findings with fix PR status, per project and organization.",
		fields: [
			{
				...API_TOKEN,
				help: "A service account token with the Org Admin role.",
				label: "Service account token",
			},
			{
				key: "org_id",
				label: "Organization ID",
				placeholder: "6d5e3c3a-2b4f-4c1e-9a7b-0f3b9e2c1d8a",
			},
			regionSelect([
				["SNYK-US-01", "https://api.snyk.io"],
				["SNYK-US-02", "https://api.us.snyk.io"],
				["SNYK-EU-01", "https://api.eu.snyk.io"],
				["SNYK-AU-01", "https://api.au.snyk.io"],
			]),
		],
		logo: "snyk.svg",
		models: ["code-findings", "repositories"],
		name: "Snyk",
		permissions: ["Service account with Org Admin or Group Viewer role"],
		products: ["Snyk Open Source", "Snyk Code", "Snyk Container", "Snyk IaC"],
		rateLimit: "1,620 requests per minute per token (REST API)",
		slug: "snyk",
		status: "ga",
		vendorDocs: "https://docs.snyk.io/snyk-api",
		writeActions: NO_WRITES,
	},
	{
		auth: "API_KEY",
		categories: ["appsec"],
		description:
			"Code, supply-chain and secrets findings from Semgrep AppSec Platform, with triage state and the rule that fired.",
		fields: [
			{
				...API_TOKEN,
				help: "Settings → Tokens → Create new token with Web API scope.",
				key: "web_api_token",
				label: "Web API token",
			},
		],
		logo: "semgrep.svg",
		models: ["code-findings", "repositories"],
		name: "Semgrep",
		permissions: ["Token with the Web API scope"],
		products: ["Semgrep Code", "Semgrep Supply Chain", "Semgrep Secrets"],
		rateLimit: "100 requests per minute",
		slug: "semgrep",
		status: "ga",
		vendorDocs: "https://semgrep.dev/api/v1/docs",
		writeActions: NO_WRITES,
	},
	{
		auth: "API_KEY",
		categories: ["appsec"],
		description:
			"Vulnerabilities and security hotspots per project and branch, from SonarQube Server or SonarQube Cloud.",
		fields: [
			baseUrl("https://sonarqube.acme.internal"),
			{
				...API_TOKEN,
				help: "A user token from My Account → Security.",
				label: "User token",
			},
		],
		logo: "sonarqube.svg",
		models: ["code-findings", "repositories"],
		name: "SonarQube",
		permissions: ["Browse permission on the projects to sync"],
		products: ["SonarQube Server", "SonarQube Cloud"],
		rateLimit: "No documented limit; SecureFabric caps at 20 rps",
		slug: "sonarqube",
		status: "ga",
		vendorDocs: "https://next.sonarqube.com/sonarqube/web_api",
		writeActions: NO_WRITES,
	},
	{
		auth: "API_KEY",
		categories: ["vulnerability"],
		description:
			"InsightVM vulnerabilities, assets and remediation projects through the Insight platform API.",
		fields: [
			regionSelect([
				["United States", "https://us.api.insight.rapid7.com"],
				["Europe", "https://eu.api.insight.rapid7.com"],
				["Canada", "https://ca.api.insight.rapid7.com"],
				["Australia", "https://au.api.insight.rapid7.com"],
				["Japan", "https://ap.api.insight.rapid7.com"],
			]),
			{ ...API_TOKEN, key: "api_key", label: "Organization API key" },
		],
		logo: "rapid7.png",
		models: ["vulnerabilities", "devices"],
		name: "Rapid7 InsightVM",
		permissions: ["Organization key, or a user key with Read Only role"],
		products: ["InsightVM", "Nexpose"],
		rateLimit: "Not published; SecureFabric backs off on 429",
		slug: "rapid7",
		status: "beta",
		vendorDocs: "https://help.rapid7.com/insightvm/en-us/api/integrations.html",
		writeActions: NO_WRITES,
	},
	{
		auth: "OAUTH2",
		categories: ["endpoint", "vulnerability"],
		description:
			"Defender for Endpoint alerts and device inventory, and Defender Vulnerability Management findings per machine.",
		fields: [TENANT_ID, CLIENT_ID, CLIENT_SECRET],
		logo: "microsoft-defender.svg",
		models: ["devices", "detections", "vulnerabilities"],
		name: "Microsoft Defender",
		permissions: [
			"Admin consent for Machine.Read.All, Alert.Read.All, Vulnerability.Read.All",
			"Machine.Isolate for device isolation (optional)",
		],
		products: [
			"Defender for Endpoint",
			"Defender Vulnerability Management",
			"Defender XDR",
		],
		rateLimit: "100 calls per minute and 1,500 per hour per tenant",
		slug: "microsoft-defender",
		status: "beta",
		vendorDocs: "https://learn.microsoft.com/defender-endpoint/api/apis-intro",
		writeActions: [ISOLATE],
	},
	{
		auth: "API_KEY",
		categories: ["endpoint", "vulnerability"],
		description:
			"Singularity threats, agent health and application vulnerabilities, with network quarantine as a write action.",
		fields: [
			baseUrl(
				"https://usea1-acme.sentinelone.net",
				"Your management console URL."
			),
			{
				...API_TOKEN,
				help: "A service user token with the Viewer role (IR Team for isolation).",
			},
		],
		logo: "sentinelone.png",
		models: ["devices", "detections", "vulnerabilities"],
		name: "SentinelOne",
		permissions: ["Service user with Viewer role at Account or Site scope"],
		products: ["Singularity Endpoint", "Singularity Vulnerability Mgmt"],
		rateLimit: "25 requests per second per token",
		slug: "sentinelone",
		status: "beta",
		vendorDocs: "https://usea1-partners.sentinelone.net/api-doc/overview",
		writeActions: [ISOLATE, RESOLVE_DETECTION],
	},
	{
		auth: "API_KEY",
		categories: ["identity"],
		description:
			"Users, groups, app assignments, MFA factors and admin roles from Okta Workforce Identity.",
		fields: [
			{
				help: "Your Okta org URL, e.g. https://acme.okta.com",
				key: "org_url",
				label: "Org URL",
				placeholder: "https://acme.okta.com",
			},
			{
				...API_TOKEN,
				help: "Security → API → Tokens, from a Read-Only Admin.",
			},
		],
		logo: "okta.svg",
		models: ["users", "groups"],
		name: "Okta",
		permissions: [
			"API token created by a Read-Only Administrator",
			"Super Admin token for user suspension (optional)",
		],
		products: ["Workforce Identity Cloud"],
		rateLimit: "Per-endpoint; /api/v1/users is 600 requests per minute",
		slug: "okta",
		status: "beta",
		vendorDocs: "https://developer.okta.com/docs/reference/core-okta-api/",
		writeActions: [SUSPEND_USER],
	},
	{
		auth: "OAUTH2",
		categories: ["identity"],
		description:
			"Users, groups, sign-in activity and MFA registration from Microsoft Entra ID through Microsoft Graph.",
		fields: [TENANT_ID, CLIENT_ID, CLIENT_SECRET],
		logo: "entra.png",
		models: ["users", "groups"],
		name: "Microsoft Entra ID",
		permissions: [
			"Application permissions: User.Read.All, Group.Read.All, AuditLog.Read.All",
			"UserAuthenticationMethod.Read.All for MFA status",
		],
		products: ["Entra ID P1", "Entra ID P2"],
		rateLimit: "Microsoft Graph throttling, per app per tenant",
		slug: "microsoft-entra",
		status: "beta",
		vendorDocs: "https://learn.microsoft.com/graph/api/resources/users",
		writeActions: [SUSPEND_USER],
	},
	{
		auth: "AWS_ROLE",
		categories: ["cloud", "vulnerability"],
		description:
			"Security Hub and Inspector findings, Config inventory and IAM Access Analyzer results across every account in the organization.",
		fields: [
			{
				help: "The role SecureFabric assumes. Create it with the CloudFormation template.",
				key: "aws_role_arn",
				label: "Role ARN",
				placeholder: "arn:aws:iam::123456789012:role/SecureFabricReadOnly",
			},
			{
				help: "Generated per connection. Paste it into the role's trust policy.",
				key: "external_id",
				label: "External ID",
				placeholder: "securefabric-7f3k9q",
			},
			{
				key: "aws_region_name",
				label: "Home region",
				options: [
					{ label: "us-east-1 (N. Virginia)", value: "us-east-1" },
					{ label: "us-west-2 (Oregon)", value: "us-west-2" },
					{ label: "eu-west-1 (Ireland)", value: "eu-west-1" },
					{ label: "eu-central-1 (Frankfurt)", value: "eu-central-1" },
					{ label: "ap-southeast-2 (Sydney)", value: "ap-southeast-2" },
				],
			},
		],
		logo: "aws.svg",
		models: ["cloud-resources", "cloud-findings", "vulnerabilities"],
		name: "AWS",
		permissions: [
			"IAM role with SecurityAudit and AWSSecurityHubReadOnlyAccess",
			"Trust policy for SecureFabric's account with your external ID",
		],
		products: ["Security Hub", "Inspector", "Config", "IAM Access Analyzer"],
		rateLimit: "Per service; Security Hub GetFindings is 3 rps",
		slug: "aws",
		status: "beta",
		vendorDocs: "https://docs.aws.amazon.com/securityhub/latest/APIReference/",
		writeActions: NO_WRITES,
	},
	{
		auth: "CLIENT_CREDENTIALS",
		categories: ["appsec"],
		description:
			"SAST, SCA, IaC and API security results from Checkmarx One, per project and scan.",
		fields: [
			regionSelect([
				["US", "https://us.ast.checkmarx.net"],
				["US2", "https://us.ast.checkmarx.net"],
				["EU", "https://eu.ast.checkmarx.net"],
				["EU2", "https://eu-2.ast.checkmarx.net"],
				["India", "https://ind.ast.checkmarx.net"],
			]),
			{ key: "tenant_name", label: "Tenant name", placeholder: "acme" },
			CLIENT_ID,
			CLIENT_SECRET,
		],
		logo: "checkmarx.svg",
		models: ["code-findings", "repositories"],
		name: "Checkmarx One",
		permissions: ["OAuth client with the ast-viewer role"],
		products: ["Checkmarx One SAST", "SCA", "KICS"],
		rateLimit: "Not published; SecureFabric caps at 10 rps",
		slug: "checkmarx",
		status: "beta",
		vendorDocs:
			"https://checkmarx.stoplight.io/docs/checkmarx-one-api-reference-guide",
		writeActions: NO_WRITES,
	},
	{
		auth: "API_KEY",
		categories: ["appsec"],
		description: "Dependency vulnerabilities and license risk from Mend SCA.",
		fields: [
			{
				key: "user_email",
				label: "User email",
				placeholder: "svc-securefabric@acme.com",
			},
			{ ...API_TOKEN, key: "user_key", label: "User key" },
			{
				key: "org_uuid",
				label: "Organization UUID",
				placeholder: "1f4d9e2a-7c3b-4a8e-b6d1-9e0f2a3c4b5d",
			},
			baseUrl("https://api-saas.mend.io"),
		],
		logo: "mend.png",
		models: ["code-findings", "repositories"],
		name: "Mend",
		permissions: ["A service user in the Read Only group"],
		products: ["Mend SCA", "Mend SAST"],
		rateLimit: "Not published",
		slug: "mend",
		status: "beta",
		vendorDocs: "https://docs.mend.io/platform/latest/mend-api-3-0",
		writeActions: NO_WRITES,
	},
	{
		auth: "CLIENT_CREDENTIALS",
		categories: ["appsec", "cloud"],
		description: "Code, dependency, container and cloud findings in one feed.",
		fields: [CLIENT_ID, CLIENT_SECRET],
		logo: "aikido.png",
		models: ["code-findings", "repositories"],
		name: "Aikido",
		permissions: ["REST API client created by a workspace admin"],
		products: ["Aikido Security"],
		rateLimit: "20 requests per minute per client",
		slug: "aikido",
		status: "beta",
		vendorDocs: "https://apidocs.aikido.dev",
		writeActions: NO_WRITES,
	},
	{
		auth: "APP",
		categories: ["appsec"],
		description:
			"Repositories, Dependabot, code scanning and secret scanning alerts, installed as a GitHub App.",
		fields: [
			{
				help: "Install the SecureFabric GitHub App on the organization and paste the installation ID.",
				key: "installation_id",
				label: "Installation ID",
				placeholder: "52814937",
			},
			{
				key: "org",
				label: "Organization",
				placeholder: "acme-corp",
			},
		],
		logo: "github.svg",
		models: ["code-findings", "repositories"],
		name: "GitHub",
		permissions: [
			"GitHub App with Metadata, Dependabot alerts, Code scanning alerts, Secret scanning alerts: Read",
		],
		products: ["GitHub Advanced Security", "Dependabot"],
		rateLimit: "15,000 requests per hour per installation (Enterprise Cloud)",
		slug: "github",
		status: "beta",
		vendorDocs: "https://docs.github.com/rest/code-scanning",
		writeActions: NO_WRITES,
	},
	{
		auth: "API_KEY",
		categories: ["appsec"],
		description:
			"Projects, vulnerability reports and merge requests from GitLab.",
		fields: [
			baseUrl("https://gitlab.com"),
			{
				...API_TOKEN,
				help: "read_api scope, Reporter role.",
				label: "Group access token",
			},
		],
		logo: "gitlab.svg",
		models: ["code-findings", "repositories"],
		name: "GitLab",
		permissions: ["Group access token with read_api, Reporter role"],
		products: ["GitLab Ultimate security dashboards"],
		rateLimit: "2,000 requests per minute (GitLab.com)",
		slug: "gitlab",
		status: "beta",
		vendorDocs: "https://docs.gitlab.com/api/vulnerabilities/",
		writeActions: NO_WRITES,
	},
	{
		auth: "OAUTH2",
		categories: ["ticketing"],
		description:
			"Issues, projects and comments from Jira Cloud. Create and update tickets through the unified Ticket model.",
		fields: [
			{
				key: "site",
				label: "Site URL",
				placeholder: "https://acme.atlassian.net",
			},
			{
				key: "email",
				label: "Account email",
				placeholder: "svc-securefabric@acme.com",
			},
			{ ...API_TOKEN, help: "id.atlassian.com → Security → API tokens." },
		],
		logo: "jira.svg",
		models: ["tickets"],
		name: "Jira",
		permissions: ["Browse projects and Create issues in target projects"],
		products: ["Jira Cloud", "Jira Service Management"],
		rateLimit: "Cost-based; roughly 100 requests per second per site",
		slug: "jira",
		status: "beta",
		vendorDocs: "https://developer.atlassian.com/cloud/jira/platform/rest/v3/",
		writeActions: [CREATE_TICKET, UPDATE_TICKET],
	},
	{
		auth: "BASIC",
		categories: ["ticketing", "grc", "asset"],
		description:
			"Incidents, vulnerability response items and CMDB configuration items from ServiceNow.",
		fields: [
			{
				key: "instance_url",
				label: "Instance URL",
				placeholder: "https://acme.service-now.com",
			},
			{ key: "username", label: "Username", placeholder: "svc_securefabric" },
			{
				key: "password",
				label: "Password",
				placeholder: "••••••••••••",
				secret: true,
			},
		],
		logo: "servicenow.png",
		models: ["tickets", "devices"],
		name: "ServiceNow",
		permissions: ["itil and sn_vul.read roles on the integration user"],
		products: ["ITSM", "Vulnerability Response", "CMDB"],
		rateLimit: "Instance-configured rate limit rules",
		slug: "servicenow",
		status: "beta",
		vendorDocs:
			"https://developer.servicenow.com/dev.do#!/reference/api/latest/rest/",
		writeActions: [CREATE_TICKET, UPDATE_TICKET],
	},
	{
		auth: "CLIENT_CREDENTIALS",
		categories: ["endpoint", "vulnerability"],
		description:
			"Endpoint inventory, patch state and vulnerability findings from Tanium.",
		fields: [baseUrl("https://acme-api.cloud.tanium.com"), { ...API_TOKEN }],
		logo: "tanium.svg",
		models: ["devices", "vulnerabilities"],
		name: "Tanium",
		permissions: ["API token with Comply and Asset read permissions"],
		products: ["Tanium Comply", "Tanium Asset"],
		rateLimit: "Not published",
		slug: "tanium",
		status: "beta",
		vendorDocs: "https://help.tanium.com/bundle/ug_gateway_cloud",
		writeActions: NO_WRITES,
	},
	{
		auth: "API_KEY",
		categories: ["cloud", "container"],
		description:
			"Agentless posture, workload vulnerability and data-risk alerts across clouds.",
		fields: [
			regionSelect([
				["US", "https://api.orcasecurity.io"],
				["EU", "https://app.eu.orcasecurity.io"],
				["Australia", "https://app.au.orcasecurity.io"],
			]),
			{ ...API_TOKEN },
		],
		logo: "orca.svg",
		models: ["cloud-findings", "cloud-resources", "vulnerabilities"],
		name: "Orca Security",
		permissions: ["API token with the Viewer role"],
		products: ["Orca Cloud Security Platform"],
		rateLimit: "Not published",
		slug: "orca",
		status: "beta",
		vendorDocs: "https://docs.orcasecurity.io/docs/orca-api",
		writeActions: NO_WRITES,
	},
	{
		auth: "CLIENT_CREDENTIALS",
		categories: ["mdm"],
		description:
			"Mac and mobile inventory, FileVault and compliance state from Jamf Pro.",
		fields: [baseUrl("https://acme.jamfcloud.com"), CLIENT_ID, CLIENT_SECRET],
		logo: "jamf.png",
		models: ["devices"],
		name: "Jamf Pro",
		permissions: ["API role with Read Computers and Read Mobile Devices"],
		products: ["Jamf Pro"],
		rateLimit: "Not published",
		slug: "jamf",
		status: "beta",
		vendorDocs: "https://developer.jamf.com/jamf-pro/reference",
		writeActions: NO_WRITES,
	},
	{
		auth: "API_KEY",
		categories: ["vulnerability", "cloud"],
		description: "Runtime-aware cloud vulnerabilities and workload exposure.",
		fields: [
			CLIENT_ID,
			CLIENT_SECRET,
			{ key: "org_id", label: "Organization ID", placeholder: "org_8h2k..." },
		],
		logo: "upwind.png",
		models: ["vulnerabilities", "cloud-resources"],
		name: "Upwind",
		permissions: ["API client with read scopes"],
		products: ["Upwind CNAPP"],
		rateLimit: "Not published",
		slug: "upwind",
		status: "beta",
		vendorDocs: "https://docs.upwind.io",
		writeActions: NO_WRITES,
	},
	{
		auth: "API_KEY",
		categories: ["siem"],
		description:
			"Signals and the log events behind them from Datadog Cloud SIEM.",
		fields: [
			regionSelect([
				["US1", "https://api.datadoghq.com"],
				["US3", "https://api.us3.datadoghq.com"],
				["US5", "https://api.us5.datadoghq.com"],
				["EU1", "https://api.datadoghq.eu"],
			]),
			{ ...API_TOKEN, key: "api_key", label: "API key" },
			{ ...API_TOKEN, key: "app_key", label: "Application key" },
		],
		logo: "datadog.svg",
		models: ["alerts"],
		name: "Datadog",
		permissions: ["Application key with security_monitoring_signals_read"],
		products: ["Cloud SIEM"],
		rateLimit: "Per endpoint; signals search is 300 per hour",
		slug: "datadog",
		status: "beta",
		vendorDocs: "https://docs.datadoghq.com/api/latest/security-monitoring/",
		writeActions: NO_WRITES,
	},
	{
		auth: "OAUTH2",
		categories: ["notifications"],
		description: "Send owner notifications and approvals to channels and DMs.",
		fields: [
			{
				...API_TOKEN,
				key: "bot_token",
				label: "Bot token",
				placeholder: "xoxb-••••",
			},
		],
		logo: "slack.svg",
		models: [],
		name: "Slack",
		permissions: ["chat:write, users:read.email, channels:read"],
		products: ["Slack"],
		rateLimit: "Tier 3: 50+ requests per minute",
		slug: "slack",
		status: "beta",
		vendorDocs: "https://api.slack.com/methods",
		writeActions: [
			{
				endpoint: "POST /v1/notifications",
				name: "Send message",
				scope: "notifications:write",
			},
		],
	},
];

interface SoonSeed {
	categories: CategoryKey[];
	description: string;
	logo?: string;
	models: ModelKey[];
	name: string;
}

/** Listed in the catalogue, not yet connectable. */
const SOON: SoonSeed[] = [
	{
		categories: ["endpoint"],
		description: "Endpoint and server detections from Sophos Central.",
		models: ["devices", "detections"],
		name: "Sophos",
	},
	{
		categories: ["endpoint"],
		description: "Managed EDR incidents and agent inventory.",
		models: ["devices", "detections"],
		name: "Huntress",
	},
	{
		categories: ["endpoint"],
		description: "Carbon Black Cloud alerts and sensor inventory.",
		models: ["devices", "detections"],
		name: "VMware Carbon Black",
	},
	{
		categories: ["endpoint", "mdm"],
		description: "Apple device inventory, compliance and EDR from Kandji.",
		models: ["devices"],
		name: "Kandji",
	},
	{
		categories: ["vulnerability"],
		description: "Local and agent scan results from Nessus Professional.",
		logo: "tenable.svg",
		models: ["vulnerabilities", "devices"],
		name: "Tenable Nessus",
	},
	{
		categories: ["vulnerability"],
		description: "Vulnerability scans for MSPs from ConnectSecure.",
		models: ["vulnerabilities", "devices"],
		name: "ConnectSecure",
	},
	{
		categories: ["vulnerability", "appsec"],
		description: "Dynamic scan issues from Burp Suite Enterprise.",
		models: ["vulnerabilities"],
		name: "PortSwigger Burp Suite",
	},
	{
		categories: ["cloud"],
		description: "Cloud posture and anomaly alerts from FortiCNAPP.",
		models: ["cloud-findings", "cloud-resources"],
		name: "Lacework",
	},
	{
		categories: ["cloud", "container"],
		description:
			"Runtime detections and image vulnerabilities from Sysdig Secure.",
		models: ["cloud-findings", "vulnerabilities"],
		name: "Sysdig",
	},
	{
		categories: ["cloud", "container"],
		description: "Image and workload findings from Aqua Platform.",
		models: ["vulnerabilities", "cloud-findings"],
		name: "Aqua Security",
	},
	{
		categories: ["cloud", "network"],
		description: "Prisma Cloud posture findings and Strata firewall policy.",
		logo: "palo-alto.svg",
		models: ["cloud-findings", "cloud-resources"],
		name: "Palo Alto Prisma Cloud",
	},
	{
		categories: ["cloud"],
		description: "Defender for Cloud recommendations and secure score.",
		logo: "azure.svg",
		models: ["cloud-findings", "cloud-resources"],
		name: "Microsoft Defender for Cloud",
	},
	{
		categories: ["cloud"],
		description: "Security Command Center findings and asset inventory.",
		logo: "gcp.svg",
		models: ["cloud-findings", "cloud-resources"],
		name: "Google Cloud",
	},
	{
		categories: ["cloud", "network"],
		description: "SSE alerts and app inventory from Netskope.",
		models: ["alerts"],
		name: "Netskope",
	},
	{
		categories: ["container"],
		description: "Image scan results from Anchore Grype.",
		models: ["vulnerabilities"],
		name: "Grype",
	},
	{
		categories: ["appsec"],
		description: "Static and dynamic analysis flaws from Veracode.",
		models: ["code-findings"],
		name: "Veracode",
	},
	{
		categories: ["appsec"],
		description: "Supply-chain risk alerts for open source packages.",
		models: ["code-findings"],
		name: "Socket",
	},
	{
		categories: ["appsec"],
		description: "Secrets incidents from GitGuardian Internal Monitoring.",
		models: ["code-findings"],
		name: "GitGuardian",
	},
	{
		categories: ["appsec"],
		description: "Pipeline-less code risk and secrets from Arnica.",
		models: ["code-findings"],
		name: "Arnica",
	},
	{
		categories: ["appsec"],
		description: "Runtime application vulnerabilities from Contrast.",
		models: ["code-findings"],
		name: "Contrast Security",
	},
	{
		categories: ["appsec", "vulnerability"],
		description: "Nuclei template findings from ProjectDiscovery Cloud.",
		models: ["vulnerabilities"],
		name: "ProjectDiscovery",
	},
	{
		categories: ["identity"],
		description: "Users, devices and MFA enrolment from Cisco Duo.",
		models: ["users"],
		name: "Duo Security",
	},
	{
		categories: ["identity", "mdm"],
		description: "Directory users, groups and managed devices.",
		logo: "jumpcloud.png",
		models: ["users", "groups", "devices"],
		name: "JumpCloud",
	},
	{
		categories: ["identity"],
		description: "Users, groups and Workspace admin roles.",
		logo: "google-workspace.png",
		models: ["users", "groups"],
		name: "Google Workspace",
	},
	{
		categories: ["identity"],
		description: "Tenants, users and connections from Auth0.",
		logo: "auth0.svg",
		models: ["users"],
		name: "Auth0",
	},
	{
		categories: ["identity"],
		description: "Members, vault access and events from 1Password Business.",
		logo: "1password.svg",
		models: ["users", "groups"],
		name: "1Password",
	},
	{
		categories: ["siem"],
		description:
			"Notable events and saved searches from Splunk Enterprise Security.",
		logo: "splunk.png",
		models: ["alerts"],
		name: "Splunk",
	},
	{
		categories: ["siem"],
		description: "Detection alerts from Elastic Security.",
		logo: "elastic.svg",
		models: ["alerts"],
		name: "Elastic",
	},
	{
		categories: ["siem"],
		description: "Cloud SIEM insights from Sumo Logic.",
		logo: "sumo-logic.png",
		models: ["alerts"],
		name: "Sumo Logic",
	},
	{
		categories: ["siem"],
		description: "Detections and alerts from Panther.",
		logo: "panther.png",
		models: ["alerts"],
		name: "Panther",
	},
	{
		categories: ["siem"],
		description: "Threat center cases from Exabeam New-Scale.",
		models: ["alerts"],
		name: "Exabeam",
	},
	{
		categories: ["siem"],
		description: "Alarms and cases from LogRhythm SIEM.",
		models: ["alerts"],
		name: "LogRhythm",
	},
	{
		categories: ["email"],
		description: "Attacks and remediated messages from Abnormal.",
		logo: "abnormal.png",
		models: ["email-threats"],
		name: "Abnormal Security",
	},
	{
		categories: ["email"],
		description: "TAP clicks, messages blocked and VAP data.",
		logo: "proofpoint.svg",
		models: ["email-threats"],
		name: "Proofpoint",
	},
	{
		categories: ["email"],
		description: "Phishing detections and post-delivery remediation.",
		models: ["email-threats"],
		name: "Material Security",
	},
	{
		categories: ["email"],
		description: "Threat remediation incidents from Mimecast.",
		models: ["email-threats"],
		name: "Mimecast",
	},
	{
		categories: ["network"],
		description: "ZIA and ZPA logs and policy from Zscaler.",
		logo: "zscaler.svg",
		models: ["alerts"],
		name: "Zscaler",
	},
	{
		categories: ["network"],
		description: "FortiGate policy and FortiAnalyzer events.",
		logo: "fortinet.svg",
		models: ["alerts"],
		name: "Fortinet",
	},
	{
		categories: ["network"],
		description: "WAF events, DNS records and Zero Trust logs.",
		logo: "cloudflare.svg",
		models: ["alerts"],
		name: "Cloudflare",
	},
	{
		categories: ["network"],
		description: "Gateway policy and threat logs from Check Point.",
		models: ["alerts"],
		name: "Check Point",
	},
	{
		categories: ["network"],
		description: "Firewall Management Center events.",
		models: ["alerts"],
		name: "Cisco Secure Firewall",
	},
	{
		categories: ["threat-intel"],
		description: "File, URL and IP reputation lookups.",
		logo: "virustotal.svg",
		models: ["indicators"],
		name: "VirusTotal",
	},
	{
		categories: ["threat-intel"],
		description: "Risk scores and actor context for indicators.",
		logo: "recorded-future.png",
		models: ["indicators"],
		name: "Recorded Future",
	},
	{
		categories: ["threat-intel"],
		description: "Compromised credentials and threat intelligence.",
		models: ["indicators"],
		name: "Flashpoint",
	},
	{
		categories: ["ticketing"],
		description: "Issues and projects from Linear.",
		logo: "linear.svg",
		models: ["tickets"],
		name: "Linear",
	},
	{
		categories: ["ticketing", "notifications"],
		description: "Incidents and on-call schedules from PagerDuty.",
		logo: "pagerduty.svg",
		models: ["tickets"],
		name: "PagerDuty",
	},
	{
		categories: ["ticketing"],
		description: "Items and boards from monday.com.",
		models: ["tickets"],
		name: "monday.com",
	},
	{
		categories: ["notifications"],
		description: "Channel and chat messages to Microsoft Teams.",
		logo: "microsoft-teams.svg",
		models: [],
		name: "Microsoft Teams",
	},
	{
		categories: ["grc"],
		description: "Failing tests and controls from Vanta.",
		logo: "vanta.png",
		models: ["controls"],
		name: "Vanta",
	},
	{
		categories: ["grc"],
		description: "Monitors and controls from Drata.",
		logo: "drata.png",
		models: ["controls"],
		name: "Drata",
	},
	{
		categories: ["grc"],
		description: "Tests and controls from Secureframe.",
		logo: "secureframe.png",
		models: ["controls"],
		name: "Secureframe",
	},
	{
		categories: ["grc"],
		description: "Issues and controls from Archer IRM.",
		logo: "archer.png",
		models: ["controls"],
		name: "Archer",
	},
	{
		categories: ["grc", "tprm"],
		description: "Vendors, assessments and controls from OneTrust.",
		logo: "onetrust.png",
		models: ["controls", "vendors"],
		name: "OneTrust",
	},
	{
		categories: ["tprm"],
		description: "Vendor risk ratings and questionnaires.",
		logo: "upguard.svg",
		models: ["vendors"],
		name: "UpGuard",
	},
	{
		categories: ["tprm"],
		description: "Security ratings and portfolio findings.",
		logo: "bitsight.png",
		models: ["vendors"],
		name: "Bitsight",
	},
	{
		categories: ["tprm"],
		description: "Scorecards and issue factors per vendor.",
		logo: "securityscorecard.svg",
		models: ["vendors"],
		name: "SecurityScorecard",
	},
	{
		categories: ["tprm"],
		description: "Cyber risk ratings and FocusTags.",
		models: ["vendors"],
		name: "Black Kite",
	},
	{
		categories: ["asset"],
		description: "Asset inventory and risk from Armis Centrix.",
		models: ["devices"],
		name: "Armis",
	},
	{
		categories: ["asset"],
		description: "The JupiterOne graph of assets and relationships.",
		models: ["devices", "cloud-resources"],
		name: "JupiterOne",
	},
	{
		categories: ["asset", "data"],
		description: "Data stores and sensitive-data findings from Cyera.",
		models: ["cloud-findings"],
		name: "Cyera",
	},
	{
		categories: ["asset", "endpoint"],
		description: "Endpoint management and patch data from Ivanti Neurons.",
		models: ["devices", "vulnerabilities"],
		name: "Ivanti",
	},
	{
		categories: ["data"],
		description: "Write unified records to Snowflake tables.",
		logo: "snowflake.svg",
		models: [],
		name: "Snowflake",
	},
	{
		categories: ["data"],
		description: "Stream security telemetry through Cribl Stream.",
		models: [],
		name: "Cribl",
	},
	{
		categories: ["bug-bounty", "vulnerability"],
		description: "Reports and program findings from HackerOne.",
		models: ["vulnerabilities"],
		name: "HackerOne",
	},
	{
		categories: ["bug-bounty"],
		description: "Submissions from Bugcrowd programs.",
		models: ["vulnerabilities"],
		name: "Bugcrowd",
	},
	{
		categories: ["mdm"],
		description: "Mobile threat detections and device risk.",
		models: ["devices", "detections"],
		name: "Lookout",
	},
];

const NON_ALNUM = /[^a-z0-9]+/gu;
const EDGE_DASHES = /^-+|-+$/gu;

function slugify(name: string): string {
	return name.toLowerCase().replace(NON_ALNUM, "-").replace(EDGE_DASHES, "");
}

export const PROVIDERS: Provider[] = [
	...LIVE,
	...SOON.map(
		(s): Provider => ({
			auth: "API_KEY",
			categories: s.categories,
			description: s.description,
			fields: [],
			logo: s.logo,
			models: s.models,
			name: s.name,
			permissions: [],
			products: [s.name],
			rateLimit: "—",
			slug: slugify(s.name),
			status: "soon",
			vendorDocs: "",
			writeActions: NO_WRITES,
		})
	),
];

const BY_SLUG = new Map(PROVIDERS.map((p) => [p.slug, p]));

export function getProvider(slug: string): Provider | undefined {
	return BY_SLUG.get(slug);
}

export function providerOrThrow(slug: string): Provider {
	const provider = BY_SLUG.get(slug);
	if (!provider) {
		throw new Error(`Unknown provider "${slug}"`);
	}
	return provider;
}

export const STATUS_LABELS: Record<ProviderStatus, string> = {
	beta: "Beta",
	ga: "GA",
	soon: "Coming soon",
};
