"""Every alert and health code links to a runbook that exists (docs/runbooks)."""

import re
from pathlib import Path

from securefabric_domain.obs import HEALTH_RUNBOOKS, RUNBOOKS
from securefabric_schema import HealthCode

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "packages" / "domain" / "src" / "securefabric_domain"


def raised_alert_names() -> set[str]:
    names: set[str] = set()
    for path in SRC.rglob("*.py"):
        text = path.read_text()
        # raise_alert(conn, "name", ...) possibly split over lines
        names |= set(re.findall(r"raise_alert\(\s*\w+,\s*\"([a-z_]+)\"", text))
    return names


def test_every_raised_alert_has_a_runbook_entry() -> None:
    raised = raised_alert_names()
    assert raised, "the scan found no alerts: the pattern is stale"
    assert raised <= RUNBOOKS.keys(), raised - RUNBOOKS.keys()


def test_every_runbook_page_exists_and_its_links_resolve() -> None:
    pages = [REPO / p for p in (*RUNBOOKS.values(), *HEALTH_RUNBOOKS.values())]
    pages.append(REPO / "docs" / "runbooks" / "README.md")
    for page in pages:
        assert page.is_file(), page
        for target in re.findall(r"\]\(([^)#:]+\.md)\)", page.read_text()):
            assert (page.parent / target).resolve().is_file(), f"{page.name} → {target}"


def test_every_unhealthy_code_has_a_health_runbook() -> None:
    needed = {c.value for c in HealthCode if c is not HealthCode.HEALTHY}
    assert needed == set(HEALTH_RUNBOOKS)
