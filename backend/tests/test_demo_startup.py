import pytest

from app.scripts.start_demo import validate_demo_configuration


def test_demo_configuration_requires_the_persistent_demo_target() -> None:
    parsed = validate_demo_configuration(
        database_url="postgresql://marketmitra_demo_user:secret@localhost:5432/marketmitra_demo",
        market_data_source="postgres",
    )
    assert parsed.database == "marketmitra_demo"
    assert parsed.username == "marketmitra_demo_user"


@pytest.mark.parametrize(
    ("database_url", "source"),
    [
        ("postgresql://postgres:secret@localhost:5432/marketmitra", "postgres"),
        ("postgresql://marketmitra_demo_user:secret@localhost:5432/marketmitra_demo", "mock"),
        ("sqlite:///marketmitra_demo.db", "postgres"),
    ],
)
def test_demo_configuration_rejects_wrong_targets(
    database_url: str, source: str
) -> None:
    with pytest.raises(ValueError):
        validate_demo_configuration(database_url=database_url, market_data_source=source)
