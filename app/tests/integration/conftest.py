"""Integration tests against a live rolling-api instance.

Requires `docker compose up` to be running. Override BASE_URL via env if needed.
"""
import os
import secrets

import httpx
import pytest


BASE_URL = os.environ.get("ROLLING_API_URL", "http://localhost:8000/api/v1")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture()
def http() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        yield client


@pytest.fixture()
def random_email() -> str:
    return f"pytest-{secrets.token_hex(4)}@example.com"


def login(http: httpx.Client, email: str, password: str) -> str:
    res = http.post("/auth/login", json={"email": email, "password": password})
    res.raise_for_status()
    return res.json()["data"]["access_token"]


@pytest.fixture()
def seeded_admin_token(http: httpx.Client) -> str:
    return login(http, "admin@example.com", "admin1234")


@pytest.fixture()
def seeded_planner_token(http: httpx.Client) -> str:
    return login(http, "planner@example.com", "planner1234")
