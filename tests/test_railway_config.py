from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_railway_uses_dockerfile_and_healthcheck() -> None:
    config = (ROOT / "railway.json").read_text()
    assert '"builder": "DOCKERFILE"' in config
    assert '"healthcheckPath": "/healthz"' in config


def test_container_binds_to_railway_port() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "0.0.0.0" in dockerfile
    assert "${PORT:-8080}" in dockerfile
