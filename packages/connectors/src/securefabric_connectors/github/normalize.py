"""Pure normalisers: one GitHub payload in, one canonical record out.

No I/O, no clock. Golden tests pin these (CDK-05).
"""

import re
from datetime import datetime
from typing import Any

from securefabric_cdk import NormalizeContext, Skip
from securefabric_connectors.github import mapping
from securefabric_schema import (
    AffectedCode,
    AffectedPackage,
    Analytic,
    CvssScore,
    FindingRecord,
    FindingState,
    FindingType,
    Group,
    Product,
    Reference,
    ResourceRecord,
    ResourceRef,
    ResourceRelated,
    ResourceState,
    ResourceType,
    Severity,
    Tag,
    VendorAttributes,
    Vulnerability,
    VulnerabilityIdentifier,
)

_CWE_TAG = re.compile(r"^external/cwe/cwe-0*(\d+)$")

# Fields never copied into vendor_data, even if GitHub starts returning them.
_NEVER_STORE = frozenset({"secret"})


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _clean(raw: dict[str, Any]) -> dict[str, Any]:
    def walk(v: Any) -> Any:
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items() if k not in _NEVER_STORE}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v

    out: dict[str, Any] = walk(raw)
    return out


def repo_key(repo_id: int | str) -> str:
    return f"repo:{repo_id}"


def repo_ref(repo: dict[str, Any]) -> ResourceRef:
    return ResourceRef(
        natural_key=repo_key(repo["id"]),
        type=ResourceType.REPOSITORY,
        role="primary",
        name=repo.get("full_name"),
        stream="repositories",
    )


def _owner_group(repo: dict[str, Any]) -> list[Group]:
    owner = repo.get("owner") or {}
    return (
        [Group(uid=str(owner["id"]), name=owner.get("login"))]
        if owner.get("id") is not None
        else []
    )


# ---------------------------------------------------------------- repositories


def _feature(block: dict[str, Any] | None, name: str) -> str | None:
    if not block or name not in block:
        return None
    status = (block[name] or {}).get("status")
    return status if status in ("enabled", "disabled") else None


def normalize_repository(raw: dict[str, Any], nctx: NormalizeContext) -> ResourceRecord:
    sa = raw.get("security_and_analysis")
    archived = bool(raw.get("archived")) or bool(raw.get("disabled"))
    return ResourceRecord(
        natural_key=repo_key(raw["id"]),
        type=ResourceType.REPOSITORY,
        state=ResourceState.INACTIVE if archived else ResourceState.ACTIVE,
        name=raw.get("full_name"),
        url=raw.get("html_url"),
        groups=_owner_group(raw),
        tags=[Tag(key="topic", value=t, source="github") for t in raw.get("topics") or []],
        data={
            "repo_url": raw.get("clone_url"),
            "default_branch": raw.get("default_branch"),
            "visibility": raw.get("visibility") or ("private" if raw.get("private") else "public"),
            "fork": raw.get("fork"),
            "archived": raw.get("archived"),
            "language": raw.get("language"),
            "pushed_at": raw.get("pushed_at"),
            "owner": (raw.get("owner") or {}).get("login"),
            "id": raw["id"],
            "security_features": None
            if sa is None
            else {
                "advanced_security": _feature(sa, "advanced_security"),
                "code_security": _feature(sa, "code_security"),
                "secret_scanning": _feature(sa, "secret_scanning"),
                "secret_scanning_push_protection": _feature(sa, "secret_scanning_push_protection"),
                "dependabot_security_updates": _feature(sa, "dependabot_security_updates"),
            },
        },
        vendor_id=str(raw["id"]),
        vendor_attributes_data={"vendor": "GITHUB", "node_id": raw.get("node_id")},
        vendor_data=_clean(raw),
    )


# ---------------------------------------------------------------- branches


def normalize_branch(raw: dict[str, Any], nctx: NormalizeContext) -> ResourceRecord | Skip:
    """``raw`` is ``{"repository": <repo>, "branch": {"name", "protected"?, "commit"?}}``."""
    repo, branch = raw["repository"], raw["branch"]
    if not branch.get("name"):
        return Skip("repository has no default branch (empty repository)")
    archived = bool(repo.get("archived"))
    return ResourceRecord(
        natural_key=f"branch:{repo['id']}:{branch['name']}",
        type=ResourceType.BRANCH,
        state=ResourceState.INACTIVE if archived else ResourceState.ACTIVE,
        name=f"{repo.get('full_name')}@{branch['name']}",
        url=f"{repo['html_url']}/tree/{branch['name']}" if repo.get("html_url") else None,
        groups=_owner_group(repo),
        data={
            "code_repo": repo.get("full_name"),
            "repo_branch_name": branch["name"],
            "is_default": branch["name"] == repo.get("default_branch"),
            "protected": branch.get("protected"),
            "repository_id": repo["id"],
        },
        vendor_id=f"{repo['id']}:{branch['name']}",
        vendor_attributes_data={
            "vendor": "GITHUB",
            "commit_sha": (branch.get("commit") or {}).get("sha"),
        },
        vendor_data=_clean(raw),
    )


# ---------------------------------------------------------------- shared alert helpers


def _skip_archived(raw: dict[str, Any], nctx: NormalizeContext) -> Skip | None:
    repo = raw.get("repository") or {}
    if repo.get("archived") and nctx.options.get("include_archived", True) is False:
        return Skip("archived repository excluded by include_archived=false")
    return None


def _branch_ref(raw: dict[str, Any], ref: str | None, nctx: NormalizeContext) -> ResourceRef | None:
    repo = raw.get("repository") or {}
    if not ref or not ref.startswith("refs/heads/"):
        return None
    name = ref.removeprefix("refs/heads/")
    tracked = nctx.options.get("branch_scope", "default") == "all" or name == repo.get(
        "default_branch"
    )
    if not tracked:
        return None
    return ResourceRef(
        natural_key=f"branch:{repo['id']}:{name}",
        type=ResourceType.BRANCH,
        role="related",
        name=f"{repo.get('full_name')}@{name}",
        stream="branches",
    )


def _login(user: dict[str, Any] | None) -> str | None:
    return (user or {}).get("login")


# ---------------------------------------------------------------- code scanning


def code_scanning_severity(rule: dict[str, Any]) -> Severity:
    level = rule.get("security_severity_level")
    if level:
        return mapping.CODE_SCANNING_SECURITY_SEVERITY.get(level, Severity.UNKNOWN)
    return mapping.CODE_SCANNING_RULE_SEVERITY.get(rule.get("severity") or "", Severity.UNKNOWN)


def normalize_code_scanning(raw: dict[str, Any], nctx: NormalizeContext) -> FindingRecord | Skip:
    if skip := _skip_archived(raw, nctx):
        return skip
    repo = raw["repository"]
    rule = raw.get("rule") or {}
    tool = raw.get("tool") or {}
    inst = raw.get("most_recent_instance") or {}
    loc = inst.get("location") or {}
    state = raw["state"]
    cwes = []
    for tag in rule.get("tags") or []:
        m = _CWE_TAG.match(tag.lower())
        if m:
            cwes.append(f"CWE-{int(m.group(1))}")
    resources = [repo_ref(repo)]
    if (b := _branch_ref(raw, inst.get("ref"), nctx)) is not None:
        resources.append(b)
    return FindingRecord(
        natural_key=f"code_scanning:{repo['id']}:{raw['number']}",
        type=FindingType.CODE,
        title=rule.get("description") or rule.get("name") or rule.get("id"),
        description=(inst.get("message") or {}).get("text"),
        severity=code_scanning_severity(rule),
        state=mapping.CODE_SCANNING_STATE[state],
        state_changed_at=_dt(raw.get("fixed_at") or raw.get("dismissed_at"))
        if state != "open"
        else None,
        has_fix=None,
        exploitable=None,
        reachability=None,
        analytic=Analytic(
            uid=rule.get("id"),
            name=rule.get("name"),
            type=tool.get("name"),
            url=rule.get("help_uri"),
        ),
        product=Product(
            name=tool.get("name"), vendor_name="GitHub" if tool.get("name") == "CodeQL" else None
        ),
        resource_related=[
            ResourceRelated(
                affected_code=AffectedCode(
                    file_path=loc.get("path"),
                    start_line_number=loc.get("start_line"),
                    end_line_number=loc.get("end_line"),
                    url=raw.get("html_url"),
                )
            )
        ]
        if loc.get("path")
        else [],
        vulnerabilities=[],
        cve_ids=[],
        vendor=VendorAttributes(
            id=str(raw["number"]),
            url=raw.get("html_url"),
            severity=rule.get("security_severity_level") or rule.get("severity"),
            state=state,
            created_at=_dt(raw.get("created_at")),
            updated_at=_dt(raw.get("updated_at")),
            vulnerability_identifiers=[
                VulnerabilityIdentifier(type="CWE", value=c) for c in sorted(set(cwes))
            ],
            data={
                "vendor": "GITHUB",
                "analysis_key": inst.get("analysis_key"),
                "category": inst.get("category"),
                "classifications": inst.get("classifications") or [],
                "commit_sha": inst.get("commit_sha"),
                "ref": inst.get("ref"),
                "environment": inst.get("environment"),
                "dismissed_reason": raw.get("dismissed_reason"),
                "dismissed_comment": raw.get("dismissed_comment"),
                "dismissed_by": _login(raw.get("dismissed_by")),
                "tool_version": tool.get("version"),
                "repository_full_name": repo.get("full_name"),
            },
        ),
        resources=resources,
        vendor_data=_clean(raw),
    )


# ---------------------------------------------------------------- secret scanning


def secret_severity(raw: dict[str, Any], nctx: NormalizeContext) -> tuple[Severity, bool]:
    """(severity, derived). UNKNOWN unless the customer opted in (part 6, section 6)."""
    choice = nctx.options.get("secret_severity", "unknown")
    if choice == "by_validity":
        return mapping.SECRET_SEVERITY_BY_VALIDITY.get(
            raw.get("validity") or "unknown", Severity.HIGH
        ), True
    if choice in mapping.SECRET_SEVERITY_FIXED:
        return mapping.SECRET_SEVERITY_FIXED[choice], True
    return Severity.UNKNOWN, False


def _secret_location(loc: dict[str, Any] | None, raw: dict[str, Any]) -> AffectedCode | None:
    if not loc:
        return None
    details = loc.get("details") or loc
    if not details.get("path"):
        return None
    return AffectedCode(
        file_path=details.get("path"),
        start_line_number=details.get("start_line"),
        end_line_number=details.get("end_line"),
        url=details.get("blob_url") or details.get("commit_url") or raw.get("html_url"),
    )


def normalize_secret_scanning(raw: dict[str, Any], nctx: NormalizeContext) -> FindingRecord | Skip:
    if skip := _skip_archived(raw, nctx):
        return skip
    repo = raw["repository"]
    state = raw["state"]
    resolution = raw.get("resolution")
    canonical = (
        FindingState.OPEN
        if state == "open"
        else mapping.SECRET_SCANNING_RESOLUTION.get(resolution, FindingState.CLOSED)
    )
    severity, derived = secret_severity(raw, nctx)
    locations = raw.get("_locations")  # attached by the stream when secret_locations=all
    if locations:
        related = [
            ResourceRelated(affected_code=c)
            for c in (_secret_location(loc, raw) for loc in locations)
            if c
        ]
    else:
        first = _secret_location(raw.get("first_location_detected"), raw)
        related = [ResourceRelated(affected_code=first)] if first else []
    return FindingRecord(
        natural_key=f"secret_scanning:{repo['id']}:{raw['number']}",
        type=FindingType.SECRET,
        title=raw.get("secret_type_display_name") or raw.get("secret_type"),
        description=None,
        severity=severity,
        state=canonical,
        state_changed_at=_dt(raw.get("resolved_at")) if state != "open" else None,
        has_fix=None,
        exploitable=None,
        reachability=None,
        analytic=Analytic(
            uid=raw.get("secret_type"),
            name=raw.get("secret_type_display_name"),
            type="secret_scanning",
        ),
        product=Product(name="Secret scanning", vendor_name="GitHub"),
        resource_related=related,
        meta_derived=["severity"] if derived else [],
        vendor=VendorAttributes(
            id=str(raw["number"]),
            url=raw.get("html_url"),
            severity=None,
            state=state,
            created_at=_dt(raw.get("created_at")),
            updated_at=_dt(raw.get("updated_at")),
            data={
                "vendor": "GITHUB",
                "validity": raw.get("validity"),
                "publicly_leaked": raw.get("publicly_leaked"),
                "multi_repo": raw.get("multi_repo"),
                "is_base64_encoded": raw.get("is_base64_encoded"),
                "has_more_locations": raw.get("has_more_locations"),
                "bypassed": raw.get("push_protection_bypassed"),
                "bypassed_at": raw.get("push_protection_bypassed_at"),
                "bypassed_by": _login(raw.get("push_protection_bypassed_by")),
                "resolution": resolution,
                "resolution_comment": raw.get("resolution_comment"),
                "resolved_by": _login(raw.get("resolved_by")),
                "provider": raw.get("provider"),
                "repository_full_name": repo.get("full_name"),
            },
        ),
        resources=[repo_ref(repo)],
        vendor_data=_clean({k: v for k, v in raw.items() if k != "_locations"}),
    )


# ---------------------------------------------------------------- dependabot


def _cvss_scores(adv: dict[str, Any]) -> list[CvssScore]:
    out: list[CvssScore] = []
    sev = adv.get("cvss_severities") or {}
    for key, version_default in (("cvss_v3", "3.1"), ("cvss_v4", "4.0")):
        block = sev.get(key) or {}
        vector = block.get("vector_string")
        if vector and block.get("score") is not None:
            version = (
                vector.split("/", 1)[0].removeprefix("CVSS:")
                if vector.startswith("CVSS:")
                else version_default
            )
            out.append(CvssScore(version=version, score=float(block["score"]), vector=vector))
    if not out:
        legacy = adv.get("cvss") or {}
        if legacy.get("vector_string") and legacy.get("score") is not None:
            vector = legacy["vector_string"]
            version = (
                vector.split("/", 1)[0].removeprefix("CVSS:")
                if vector.startswith("CVSS:")
                else "3.1"
            )
            out.append(CvssScore(version=version, score=float(legacy["score"]), vector=vector))
    return out


def normalize_dependabot(raw: dict[str, Any], nctx: NormalizeContext) -> FindingRecord | Skip:
    if skip := _skip_archived(raw, nctx):
        return skip
    repo = raw["repository"]
    adv = raw.get("security_advisory") or {}
    vuln = raw.get("security_vulnerability") or {}
    dep = raw.get("dependency") or {}
    pkg = dep.get("package") or vuln.get("package") or {}
    state = raw["state"]
    patched = (vuln.get("first_patched_version") or {}).get("identifier")
    # GitHub asserts fix availability only through security_vulnerability.first_patched_version:
    # explicitly null means "no fix"; an absent field is no assertion at all (NORM-06/09).
    has_fix = (patched is not None) if "first_patched_version" in vuln else None
    cve = adv.get("cve_id")
    uid = cve or adv.get("ghsa_id")
    vulns = (
        [
            Vulnerability(
                uid=uid,
                description=adv.get("summary"),
                published=_dt(adv.get("published_at")),
                last_modified=_dt(adv.get("updated_at")),
                cvss_scores=_cvss_scores(adv),
                weaknesses=[c["cwe_id"] for c in adv.get("cwes") or [] if c.get("cwe_id")],
                references=[
                    Reference(url=r["url"], source="github")
                    for r in adv.get("references") or []
                    if r.get("url")
                ],
                source_identifier=adv.get("ghsa_id"),
            )
        ]
        if uid
        else []
    )
    # Spike S9: GitHub's schema carries `reachability.verdict` (code-level reachability).
    verdict = (raw.get("reachability") or {}).get("verdict")
    reachability = mapping.DEPENDABOT_REACHABILITY.get(verdict) if verdict else None
    return FindingRecord(
        natural_key=f"dependabot:{repo['id']}:{raw['number']}",
        type=FindingType.DEPENDENCY,
        title=adv.get("summary"),
        description=adv.get("description"),
        severity=mapping.DEPENDABOT_SEVERITY.get(
            adv.get("severity") or vuln.get("severity") or "", Severity.UNKNOWN
        ),
        state=mapping.DEPENDABOT_STATE[state],
        state_changed_at=_dt(
            raw.get("fixed_at") or raw.get("dismissed_at") or raw.get("auto_dismissed_at")
        )
        if state != "open"
        else None,
        has_fix=has_fix,
        exploitable=None,
        reachability=reachability,
        remediation=f"Upgrade `{pkg.get('name')}` to `{patched}` or later." if patched else None,
        product=Product(name="Dependabot", vendor_name="GitHub"),
        resource_related=[
            ResourceRelated(
                affected_package=AffectedPackage(
                    name=pkg.get("name"),
                    package_manager=pkg.get("ecosystem"),
                    version=None,
                    reachability=reachability,
                    fixed_version=patched,
                    path=dep.get("manifest_path"),
                )
            )
        ],
        vulnerabilities=vulns,
        cve_ids=[cve] if cve else [],
        vendor=VendorAttributes(
            id=str(raw["number"]),
            url=raw.get("html_url"),
            severity=adv.get("severity"),
            state=state,
            created_at=_dt(raw.get("created_at")),
            updated_at=_dt(raw.get("updated_at")),
            vulnerability_identifiers=[
                VulnerabilityIdentifier(type=i["type"], value=i["value"])
                for i in adv.get("identifiers") or []
                if i.get("type") and i.get("value")
            ],
            data={
                "vendor": "GITHUB",
                "manifest_path": dep.get("manifest_path"),
                "scope": dep.get("scope"),
                "relationship": dep.get("relationship"),
                "vulnerable_version_range": vuln.get("vulnerable_version_range"),
                "dismissed_reason": raw.get("dismissed_reason"),
                "dismissed_comment": raw.get("dismissed_comment"),
                "dismissed_by": _login(raw.get("dismissed_by")),
                "ghsa_id": adv.get("ghsa_id"),
                "epss": adv.get("epss"),
                "published_at": adv.get("published_at"),
                "withdrawn_at": adv.get("withdrawn_at"),
                "repository_full_name": repo.get("full_name"),
            },
        ),
        resources=[repo_ref(repo)],
        vendor_data=_clean(raw),
    )


NORMALIZERS = {
    "code_scanning": normalize_code_scanning,
    "secret_scanning": normalize_secret_scanning,
    "dependabot": normalize_dependabot,
}
