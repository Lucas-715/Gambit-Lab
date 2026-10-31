"""
Pytest configuration and environment setup for Gambit Lab Nocturne (R1.0).
Loads .env if present without logging or exposing secrets.
Isolates unit/integration suites from burning live Gemini quota by default,
while keeping tests/live/ 100% live against Google Gemini API.
"""
import os
import pytest


def pytest_configure(config):
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k and k not in os.environ:
                        os.environ[k] = v


@pytest.fixture(autouse=True)
def isolate_non_live_tests(request, monkeypatch):
    """
    Evita consumo acidental da cota diária do Gemini em testes unitários/integração determinísticos.
    Testes em tests/live/ (ou testes que definem GAMBIT_FORCE_DEMO=0) usam Gemini real.
    """
    fspath = str(request.node.fspath).replace("\\", "/")
    if "/tests/live/" in fspath:
        monkeypatch.setenv("GAMBIT_FORCE_DEMO", "0")
    else:
        monkeypatch.setenv("GAMBIT_FORCE_DEMO", "1")
