from app import main
from app.api import legacy_router


def test_main_preserves_legacy_public_exports() -> None:
    assert main.events is legacy_router.events
    assert main.demo_trip is legacy_router.demo_trip
    assert main.report is legacy_router.report
    assert main.build_demo_trip is legacy_router.build_demo_trip
    assert main.simulation is legacy_router.simulation
    assert set(main.__all__) == {
        "app",
        "create_app",
        "build_demo_trip",
        "demo_trip",
        "events",
        "report",
        "simulation",
    }
