import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.platform.models import TenantRecord
from intent_hub.platform.workspace import TenantWorkspaceResolver
from intent_hub.tenant.components import TenantComponentRegistry
from intent_hub.tenant.context import TenantContext


@pytest.fixture
def test_dir():
    path = Path(__file__).parent / ".tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class DummyEncoder:
    def __init__(self, service_url: str, batch_size: int):
        self.service_url = service_url
        self.batch_size = batch_size
        self.dimensions = 3


class DummyQdrantClient:
    def __init__(self, url: str, collection_name: str, dimensions: int, api_key=None):
        self.url = url
        self.collection_name = collection_name
        self.dimensions = dimensions
        self.api_key = api_key


def build_context(test_dir: Path, tenant_id: str) -> TenantContext:
    tenant = TenantRecord(
        tenant_id=tenant_id,
        name=f"Tenant {tenant_id}",
        status="active",
        qdrant_collection=f"collection_{tenant_id}",
        access_codes=[],
        skill_sources=[],
    )
    workspace = TenantWorkspaceResolver(test_dir, tenant).resolve()
    return TenantContext.from_tenant_record(tenant, workspace)


def test_tenant_component_registry_reuses_same_manager_for_same_tenant(test_dir):
    registry = TenantComponentRegistry(
        encoder_factory=DummyEncoder,
        qdrant_client_factory=DummyQdrantClient,
    )
    context = build_context(test_dir, "team_alpha")

    manager_a = registry.get(context)
    manager_b = registry.get(context)

    assert manager_a is manager_b


def test_tenant_component_registry_isolates_route_manager_by_tenant(test_dir):
    registry = TenantComponentRegistry(
        encoder_factory=DummyEncoder,
        qdrant_client_factory=DummyQdrantClient,
    )
    context_a = build_context(test_dir, "team_alpha")
    context_b = build_context(test_dir, "team_beta")

    manager_a = registry.get(context_a)
    manager_b = registry.get(context_b)

    assert manager_a is not manager_b
    assert manager_a.route_manager.config_path.endswith("team_alpha\\routes.json")
    assert manager_b.route_manager.config_path.endswith("team_beta\\routes.json")
    assert manager_a.qdrant_client.collection_name == "collection_team_alpha"
    assert manager_b.qdrant_client.collection_name == "collection_team_beta"


def test_tenant_component_manager_reads_tenant_settings_file(test_dir):
    registry = TenantComponentRegistry(
        encoder_factory=DummyEncoder,
        qdrant_client_factory=DummyQdrantClient,
    )
    context = build_context(test_dir, "team_alpha")
    context.settings_path.parent.mkdir(parents=True, exist_ok=True)
    context.settings_path.write_text(
        """
{
  "EMBEDDING_SERVICE_URL": "http://tenant-embedding:3000",
  "BATCH_SIZE": 16,
  "QDRANT_URL": "http://tenant-qdrant:6333",
  "QDRANT_API_KEY": "tenant-secret"
}
        """.strip(),
        encoding="utf-8",
    )

    manager = registry.get(context)
    manager.ensure_ready()

    assert manager.encoder.service_url == "http://tenant-embedding:3000"
    assert manager.encoder.batch_size == 16
    assert manager.qdrant_client.url == "http://tenant-qdrant:6333"
    assert manager.qdrant_client.api_key == "tenant-secret"
