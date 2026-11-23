"""First-party connectors: GITHUB and SANDBOX.

Each connector lives entirely in its own subpackage (manifest, module, mapping,
fixtures, golden output, docs) and imports only ``securefabric_cdk`` and
``securefabric_schema`` (CDK-03, enforced by ``tests/test_boundaries.py``).
"""

from securefabric_cdk.connector import Connector


def all_connectors() -> list[type[Connector]]:
    from securefabric_connectors.github.connector import GitHubConnector
    from securefabric_connectors.sandbox.connector import (
        SandboxClientCredentialsConnector,
        SandboxConnector,
        SandboxOAuthConnector,
    )

    return [
        GitHubConnector,
        SandboxConnector,
        SandboxOAuthConnector,
        SandboxClientCredentialsConnector,
    ]
