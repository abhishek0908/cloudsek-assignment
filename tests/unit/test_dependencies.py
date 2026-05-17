from app.dependencies import get_metadata_service
from app.services.metadata import MetadataService


class TestDependencies:

    def test_returns_service_with_all_deps(self):
        service = get_metadata_service()
        assert isinstance(service, MetadataService)
        assert service.repository is not None
        assert service.fetch_service is not None
        assert service.worker is not None
