def test_health(http):
    res = http.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["status"] in ("ok", "degraded")
    assert "X-Request-Id" in res.headers


def test_register_login_me(http, random_email):
    res = http.post(
        "/auth/register",
        json={"email": random_email, "password": "password1234"},
    )
    assert res.status_code == 201

    res = http.post(
        "/auth/login",
        json={"email": random_email, "password": "password1234"},
    )
    assert res.status_code == 200
    tokens = res.json()["data"]
    assert tokens["access_token"] and tokens["refresh_token"]

    res = http.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert res.status_code == 200
    assert res.json()["data"]["email"] == random_email


def test_duplicate_register_conflict(http, random_email):
    http.post("/auth/register", json={"email": random_email, "password": "password1234"})
    res = http.post(
        "/auth/register", json={"email": random_email, "password": "password1234"}
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_admin_endpoint_forbidden_to_participant(http, random_email):
    http.post("/auth/register", json={"email": random_email, "password": "password1234"})
    tok = http.post(
        "/auth/login", json={"email": random_email, "password": "password1234"}
    ).json()["data"]["access_token"]
    res = http.get("/admin/dashboard", headers={"Authorization": f"Bearer {tok}"})
    assert res.status_code == 403


def test_admin_dashboard_ok(http, seeded_admin_token):
    res = http.get(
        "/admin/dashboard",
        headers={"Authorization": f"Bearer {seeded_admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert "total_users" in data and isinstance(data["rooms_by_status"], dict)
