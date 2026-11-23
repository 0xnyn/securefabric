"""Enrichment: the global CVE mirror (ENR-01..ENR-06; part 7 section 6).

Sources, each a maintenance job writing ``data.cve`` / ``data.advisory_alias``:

- **KEV** (CISA Known Exploited Vulnerabilities catalogue): whole feed, daily.
- **EPSS** (FIRST): scores for every CVE our findings reference, daily.
- **NVD** (API 2.0): descriptions, CVSS, CWE, references. Incremental by
  last-modified window from a stored cursor, plus a backfill of CVEs our findings
  reference but the mirror lacks.
- **Aliases**: GHSA → CVE from vendor identifiers (Dependabot sends both), and from
  OSV for GHSA-only advisories.

Enrichment is joined at read time: a new KEV listing appears on every affected
finding immediately, with no fan-out rewrite of tenant rows (and no flood of
``updated_at`` changes). Vendor-supplied values in ``vulnerabilities[]`` always win
(ENR-05); enrichment is a separate, clearly-ours block.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2

from securefabric_core import get_logger
from securefabric_db import fetch_all, fetch_one, system_tx
from securefabric_domain.runtime import Platform

log = get_logger(__name__)

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_URL = "https://api.first.org/data/v1/epss"
NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
OSV_URL = "https://api.osv.dev/v1/vulns/"
NVD_WINDOW = timedelta(days=7)  # NVD allows up to 120 days per window


def _client(platform: Platform) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        transport=platform.vendor_transport(),
        timeout=60.0,
        follow_redirects=True,
        headers={"User-Agent": "SecureFabric-Enrichment/1"},
    )


def _dt(v: str | None) -> datetime | None:
    if not v:
        return None
    d = datetime.fromisoformat(v.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=UTC)


async def referenced_cves(platform: Platform) -> list[str]:
    async with system_tx(platform.sys_pool) as conn:
        rows = await fetch_all(
            conn,
            "select distinct unnest(cve_ids) as c from data.vulnerability_finding where deleted_at is null",
        )
        aliased = await fetch_all(conn, "select distinct a.cve_id as c from data.advisory_alias a")
    return sorted({r["c"] for r in rows} | {r["c"] for r in aliased})


async def kev(platform: Platform) -> dict[str, Any]:
    async with _client(platform) as c:
        resp = await c.get(KEV_URL)
        resp.raise_for_status()
        feed = resp.json()
    items = feed.get("vulnerabilities") or []
    async with system_tx(platform.sys_pool) as conn:
        await conn.execute(
            "update data.cve set kev = null where kev is not null and not (cve_id = any(%s))",
            ([i["cveID"] for i in items],),
        )
        for i in items:
            entry = {
                k: i.get(k)
                for k in (
                    "vendorProject",
                    "product",
                    "vulnerabilityName",
                    "dateAdded",
                    "shortDescription",
                    "requiredAction",
                    "dueDate",
                    "knownRansomwareCampaignUse",
                )
            }
            await conn.execute(
                """insert into data.cve (cve_id, kev, updated_at) values (%s, %s, now())
                   on conflict (cve_id) do update set kev = excluded.kev, updated_at = now()""",
                (i["cveID"], json.dumps(entry)),
            )
        await _cursor(
            conn, "kev", {"catalog_version": feed.get("catalogVersion"), "count": len(items)}
        )
    return {"kev_entries": len(items), "catalog_version": feed.get("catalogVersion")}


async def epss(platform: Platform, cves: list[str] | None = None) -> dict[str, Any]:
    cves = cves if cves is not None else await referenced_cves(platform)
    updated = 0
    async with _client(platform) as c:
        for i in range(0, len(cves), 100):
            batch = cves[i : i + 100]
            resp = await c.get(EPSS_URL, params={"cve": ",".join(batch)})
            if resp.status_code != 200:
                continue
            async with system_tx(platform.sys_pool) as conn:
                for d in resp.json().get("data") or []:
                    await conn.execute(
                        """insert into data.cve (cve_id, epss, updated_at) values (%s, %s, now())
                           on conflict (cve_id) do update set epss = excluded.epss, updated_at = now()""",
                        (
                            d["cve"],
                            json.dumps(
                                {
                                    "epss": float(d["epss"]),
                                    "percentile": float(d["percentile"]),
                                    "date": d.get("date"),
                                }
                            ),
                        ),
                    )
                    updated += 1
    return {"epss_updated": updated}


def _nvd_row(cve: dict[str, Any]) -> dict[str, Any]:
    desc = next((d["value"] for d in cve.get("descriptions") or [] if d.get("lang") == "en"), None)
    metrics = cve.get("metrics") or {}
    cvss = {}
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for m in metrics.get(key) or []:
            data = m.get("cvssData") or {}
            if m.get("type") == "Primary" or key not in cvss:
                cvss[key] = {
                    "version": data.get("version"),
                    "score": data.get("baseScore"),
                    "vector": data.get("vectorString"),
                    "severity": data.get("baseSeverity") or m.get("baseSeverity"),
                    "source": m.get("source"),
                }
    cwe = sorted(
        {
            d["value"]
            for w in cve.get("weaknesses") or []
            for d in w.get("description") or []
            if d.get("value", "").startswith("CWE-")
        }
    )
    refs = [
        {"url": r["url"], "source": r.get("source"), "tags": r.get("tags") or []}
        for r in cve.get("references") or []
    ][:50]
    return {
        "cve_id": cve["id"],
        "description": desc,
        "cvss": cvss,
        "cwe": cwe,
        "references": refs,
        "published_at": _dt(cve.get("published")),
        "modified_at": _dt(cve.get("lastModified")),
    }


async def _store_nvd(platform: Platform, rows: list[dict[str, Any]]) -> None:
    async with system_tx(platform.sys_pool) as conn:
        for r in rows:
            await conn.execute(
                """insert into data.cve (cve_id, description, cvss, cwe, "references", published_at, modified_at,
                                         source_modified_at, updated_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, now())
                   on conflict (cve_id) do update set description = excluded.description, cvss = excluded.cvss,
                       cwe = excluded.cwe, "references" = excluded."references", published_at = excluded.published_at,
                       modified_at = excluded.modified_at, source_modified_at = excluded.source_modified_at,
                         updated_at = now()""",
                (
                    r["cve_id"],
                    r["description"],
                    json.dumps(r["cvss"]),
                    r["cwe"],
                    json.dumps(r["references"]),
                    r["published_at"],
                    r["modified_at"],
                    r["modified_at"],
                ),
            )


def _nvd_headers(platform: Platform) -> dict[str, str]:
    key = platform.settings.nvd_api_key
    return {"apiKey": key.get_secret_value()} if key else {}


async def nvd_referenced(platform: Platform, *, limit: int = 200) -> dict[str, Any]:
    """Backfill CVEs our findings reference that the mirror has no NVD data for."""
    async with system_tx(platform.sys_pool) as conn:
        missing = [
            r["c"]
            for r in await fetch_all(
                conn,
                """select c from (select distinct unnest(cve_ids) as c from data.vulnerability_finding where
                  deleted_at is null) f
                where not exists (select 1 from data.cve m where m.cve_id = f.c and m.modified_at is not null) limit
                  %s""",
                (limit,),
            )
        ]
    stored = 0
    async with _client(platform) as c:
        for cve_id in missing:
            resp = await c.get(NVD_URL, params={"cveId": cve_id}, headers=_nvd_headers(platform))
            if resp.status_code == 200:
                vulns = resp.json().get("vulnerabilities") or []
                if vulns:
                    await _store_nvd(platform, [_nvd_row(vulns[0]["cve"])])
                    stored += 1
            await asyncio.sleep(
                0.7 if _nvd_headers(platform) else 6.5
            )  # NVD: 50 / 30 s with a key, 5 / 30 s without
    return {"nvd_backfilled": stored, "missing": len(missing)}


async def nvd_incremental(platform: Platform) -> dict[str, Any]:
    """Advance the mirror by last-modified windows from the stored cursor."""
    now = platform.clock.now()
    async with system_tx(platform.sys_pool) as conn:
        cur = await fetch_one(conn, "select value from data.enrichment_cursor where source = 'nvd'")
    start = _dt((cur or {}).get("value", {}).get("last_mod_end")) or now - NVD_WINDOW
    end = min(start + NVD_WINDOW, now)
    total = 0
    async with _client(platform) as c:
        index = 0
        while True:
            resp = await c.get(
                NVD_URL,
                headers=_nvd_headers(platform),
                params={
                    "lastModStartDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "lastModEndDate": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "startIndex": index,
                    "resultsPerPage": 2000,
                },
            )
            if resp.status_code != 200:
                return {"nvd_error": resp.status_code}
            body = resp.json()
            rows = [_nvd_row(v["cve"]) for v in body.get("vulnerabilities") or []]
            await _store_nvd(platform, rows)
            total += len(rows)
            index += len(rows)
            if not rows or index >= int(body.get("totalResults", 0)):
                break
    async with system_tx(platform.sys_pool) as conn:
        await _cursor(conn, "nvd", {"last_mod_end": end.isoformat()})
    return {"nvd_updated": total, "window_end": end.isoformat()}


async def aliases(platform: Platform) -> dict[str, Any]:
    """GHSA → CVE: from vendor identifiers first, then OSV for GHSA-only advisories (ENR-06)."""
    async with system_tx(platform.sys_pool) as conn:
        pairs = await fetch_all(
            conn,
            """select distinct g->>'value' as ghsa, c->>'value' as cve
                 from data.vulnerability_finding f,
                      jsonb_array_elements(coalesce(f.vendor_identifiers, '[]')) g,
                      jsonb_array_elements(coalesce(f.vendor_identifiers, '[]')) c
                where g->>'type' = 'GHSA' and c->>'type' = 'CVE'""",
        )
        for p in pairs:
            await conn.execute(
                "insert into data.advisory_alias (alias, cve_id, source) values (%s, %s, 'vendor') "
                "on conflict (alias) do nothing",
                (p["ghsa"], p["cve"].upper()),
            )
        orphans = [
            r["ghsa"]
            for r in await fetch_all(
                conn,
                """select distinct g->>'value' as ghsa from data.vulnerability_finding f,
                      jsonb_array_elements(coalesce(f.vendor_identifiers, '[]')) g
                where g->>'type' = 'GHSA' and cardinality(f.cve_ids) = 0
                  and not exists (select 1 from data.advisory_alias a where a.alias = g->>'value')""",
            )
        ]
    found = 0
    async with _client(platform) as c:
        for ghsa in orphans[:200]:
            resp = await c.get(OSV_URL + ghsa)
            if resp.status_code != 200:
                continue
            cves = [a for a in resp.json().get("aliases") or [] if a.startswith("CVE-")]
            if cves:
                async with system_tx(platform.sys_pool) as conn:
                    await conn.execute(
                        "insert into data.advisory_alias (alias, cve_id, source) values (%s, %s, 'osv') "
                        "on conflict (alias) do nothing",
                        (ghsa, cves[0]),
                    )
                found += 1
    return {"vendor_pairs": len(pairs), "osv_resolved": found, "ghsa_only": len(orphans)}


async def _cursor(conn: Any, source: str, value: dict[str, Any]) -> None:
    await conn.execute(
        """insert into data.enrichment_cursor (source, value) values (%s, %s)
                          on conflict (source) do update set value = excluded.value, updated_at = now()""",
        (source, json.dumps(value)),
    )


async def run_all(platform: Platform) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, fn in (
        ("aliases", aliases),
        ("kev", kev),
        ("epss", epss),
        ("nvd_referenced", nvd_referenced),
    ):
        try:
            out[name] = await fn(platform)
        except Exception as exc:
            log.warning("enrichment_failed", source=name, error=type(exc).__name__)
            out[name] = {"error": type(exc).__name__}
    return out
