"""GitHub → canonical mapping tables, as data (docs/plan/06-github-connector.md, section 6).

Published per-connector mapping docs are generated from these tables (NORM-10).
"""

from securefabric_schema import FindingState, Reachability, Severity

# ---------------------------------------------------------------- code scanning

CODE_SCANNING_SECURITY_SEVERITY = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
}
# When security_severity_level is null (a non-security rule).
CODE_SCANNING_RULE_SEVERITY = {
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "note": Severity.LOW,
    "none": Severity.INFO,
}
CODE_SCANNING_STATE = {
    "open": FindingState.OPEN,
    "fixed": FindingState.CLOSED,
    "dismissed": FindingState.IGNORED,
}

# ---------------------------------------------------------------- secret scanning

SECRET_SCANNING_RESOLUTION = {
    None: FindingState.CLOSED,
    "revoked": FindingState.CLOSED,
    "pattern_deleted": FindingState.CLOSED,
    "pattern_edited": FindingState.CLOSED,
    "false_positive": FindingState.IGNORED,
    "wont_fix": FindingState.IGNORED,
    "used_in_tests": FindingState.IGNORED,
}
SECRET_SEVERITY_BY_VALIDITY = {
    "active": Severity.CRITICAL,
    "unknown": Severity.HIGH,
    "inactive": Severity.LOW,
}
SECRET_SEVERITY_FIXED = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
}

# ---------------------------------------------------------------- dependabot

DEPENDABOT_SEVERITY = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "moderate": Severity.MEDIUM,
    "low": Severity.LOW,
}
# Dependabot reachability verdict (code-level reachability). "unavailable" (not computed
# yet) and "disabled" (analysis off) are absent from the table: the finding says null,
# never a guess (NORM-06).
DEPENDABOT_REACHABILITY = {
    "reachable": Reachability.REACHABLE,
    "unreachable": Reachability.UNREACHABLE,
    "potentially_reachable": Reachability.POTENTIALLY_REACHABLE,
}
DEPENDABOT_STATE = {
    "open": FindingState.OPEN,
    "fixed": FindingState.CLOSED,
    "dismissed": FindingState.IGNORED,
    "auto_dismissed": FindingState.IGNORED,
}

# ---------------------------------------------------------------- write-back (part 6, section 10)
# (canonical state, canonical reason) -> request body, per family. Absent = not expressible.

WRITE_BACK = {
    "code_scanning": {
        ("IGNORED", "false_positive"): {"state": "dismissed", "dismissed_reason": "false positive"},
        ("IGNORED", "accepted_risk"): {"state": "dismissed", "dismissed_reason": "won't fix"},
        ("IGNORED", "test_code"): {"state": "dismissed", "dismissed_reason": "used in tests"},
        ("OPEN", None): {"state": "open"},
    },
    "secret_scanning": {
        ("IGNORED", "false_positive"): {"state": "resolved", "resolution": "false_positive"},
        ("IGNORED", "accepted_risk"): {"state": "resolved", "resolution": "wont_fix"},
        ("IGNORED", "test_code"): {"state": "resolved", "resolution": "used_in_tests"},
        ("CLOSED", "revoked"): {"state": "resolved", "resolution": "revoked"},
        ("OPEN", None): {"state": "open"},
    },
    "dependabot": {
        ("IGNORED", "false_positive"): {"state": "dismissed", "dismissed_reason": "inaccurate"},
        ("IGNORED", "accepted_risk"): {"state": "dismissed", "dismissed_reason": "tolerable_risk"},
        ("IGNORED", "test_code"): {"state": "dismissed", "dismissed_reason": "not_used"},
        ("OPEN", None): {"state": "open"},
    },
}
COMMENT_FIELD = {
    "code_scanning": "dismissed_comment",
    "secret_scanning": "resolution_comment",
    "dependabot": "dismissed_comment",
}
COMMENT_MAX = 280

FAMILY_PATH = {
    "code_scanning": "code-scanning/alerts",
    "secret_scanning": "secret-scanning/alerts",
    "dependabot": "dependabot/alerts",
}
STREAM_FAMILY = {
    "code_scanning_alerts": "code_scanning",
    "secret_scanning_alerts": "secret_scanning",
    "dependabot_alerts": "dependabot",
}
FAMILY_STREAM = {v: k for k, v in STREAM_FAMILY.items()}
FAMILY_PERMISSION = {
    "code_scanning": "security_events",
    "secret_scanning": "secret_scanning_alerts",
    "dependabot": "vulnerability_alerts",
}
STREAM_PERMISSION = {
    "repositories": "metadata",
    "branches": "metadata",
    **{FAMILY_STREAM[f]: p for f, p in FAMILY_PERMISSION.items()},
}
