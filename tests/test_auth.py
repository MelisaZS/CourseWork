"""Login, password hashing and role-based access tests."""

import pytest

import agent.router as router
import app as app_module
import config
from auth.decorators import is_safe_next
from auth.users import (
    allowed_routes,
    can_upload,
    check_login,
    create_demo_users,
    create_user,
    hash_password,
    list_users,
    verify_password,
)
from db.database import run_query


@pytest.fixture(autouse=True)
def fast_bcrypt(monkeypatch):
    monkeypatch.setattr(config, "BCRYPT_ROUNDS", 4)


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "company.db"
    monkeypatch.setattr(config, "DB_PATH", path)
    create_user("ayse", "Guclu.Sifre1", "admin", path)
    create_user("mehmet", "Guclu.Sifre2", "employee", path)
    create_user("misafir", "Guclu.Sifre3", "guest", path)
    return path


@pytest.fixture
def client(db):
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


def login(client, username, password, next_url=""):
    return client.post("/login", data={"username": username, "password": password, "next": next_url})


# --- passwords and users

def test_password_is_hashed_not_stored(db):
    stored = run_query("SELECT password_hash FROM users WHERE username = 'ayse'", db_path=db)["rows"][0][0]
    assert stored != "Guclu.Sifre1"
    assert stored.startswith("$2")
    assert verify_password("Guclu.Sifre1", stored)
    assert not verify_password("yanlis-sifre", stored)


def test_same_password_gets_different_hashes():
    assert hash_password("Ayni.Sifre1") != hash_password("Ayni.Sifre1")


def test_check_login(db):
    assert check_login("ayse", "Guclu.Sifre1", db) == {"id": 1, "username": "ayse", "role": "admin"}
    assert check_login("ayse", "yanlis-sifre", db) is None
    assert check_login("olmayan", "Guclu.Sifre1", db) is None
    assert check_login("", "", db) is None


def test_create_user_validation(db):
    with pytest.raises(ValueError, match="zaten var"):
        create_user("ayse", "Baska.Sifre1", "admin", db)
    with pytest.raises(ValueError, match="Geçersiz rol"):
        create_user("yeni", "Baska.Sifre1", "superuser", db)
    with pytest.raises(ValueError, match="en az 8"):
        create_user("yeni", "kisa", "guest", db)


def test_list_users_hides_password_hashes(db):
    users = list_users(db)
    assert [u["username"] for u in users] == ["ayse", "mehmet", "misafir"]
    assert all("password_hash" not in u for u in users)


def test_demo_users_are_created_once(tmp_path):
    path = tmp_path / "demo.db"
    assert create_demo_users(path) == ["admin", "calisan", "misafir"]
    assert create_demo_users(path) == []
    assert check_login("admin", "Admin.2026!", path)["role"] == "admin"


def test_role_permissions():
    assert allowed_routes("admin") == ("db", "doc", "web")
    assert "db" not in allowed_routes("guest")
    assert allowed_routes("bilinmeyen") == ()
    assert can_upload("employee") and not can_upload("guest")


# --- login pages

def test_pages_require_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_and_logout(client):
    response = login(client, "ayse", "Guclu.Sifre1")
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session["user"]["role"] == "admin"

    client.post("/logout")
    with client.session_transaction() as session:
        assert "user" not in session
    assert client.get("/").status_code == 302


def test_wrong_password_shows_error(client):
    response = login(client, "ayse", "yanlis-sifre")
    assert response.status_code == 401
    assert "Kullanıcı adı veya şifre hatalı." in response.get_data(as_text=True)
    with client.session_transaction() as session:
        assert "user" not in session


def test_redirect_after_login_only_to_own_site(client):
    assert login(client, "ayse", "Guclu.Sifre1", "/?x=1").headers["Location"] == "/?x=1"
    client.post("/logout")
    assert login(client, "ayse", "Guclu.Sifre1", "//evil.com").headers["Location"] == "/"
    assert not is_safe_next("https://evil.com")
    assert is_safe_next("/upload")


# --- role-based access

def test_guest_cannot_upload(client):
    login(client, "misafir", "Guclu.Sifre3")
    response = client.post("/upload", data={})
    assert response.status_code == 403
    assert "yetkiniz yok" in response.get_data(as_text=True)


def test_guest_database_question_is_denied(client, monkeypatch):
    monkeypatch.setattr(router, "route", lambda question: "db")

    def must_not_run(question):
        raise AssertionError("Text-to-SQL should not run for a guest")

    monkeypatch.setattr(router, "answer_from_db", must_not_run)
    login(client, "misafir", "Guclu.Sifre3")
    html = client.post("/", data={"question": "Kaç müşterimiz var?"}).get_data(as_text=True)
    assert router.ACCESS_DENIED in html


def test_employee_database_question_is_answered(client, monkeypatch):
    monkeypatch.setattr(router, "route", lambda question: "db")
    monkeypatch.setattr(
        router,
        "answer_from_db",
        lambda question: {"answer": "Sonuç: 200", "sql": "SELECT COUNT(*) FROM customers;",
                          "columns": ["n"], "rows": [[200]]},
    )
    login(client, "mehmet", "Guclu.Sifre2")
    html = client.post("/", data={"question": "Kaç müşterimiz var?"}).get_data(as_text=True)
    assert "Sonuç: 200" in html
    assert "mehmet" in html


def test_router_without_role_limit_keeps_old_behaviour(monkeypatch):
    monkeypatch.setattr(router, "route", lambda question: "web")
    monkeypatch.setattr(router, "answer_from_web", lambda question: {"answer": "ok", "sources": []})
    assert router.answer("soru")["answer"] == "ok"
    assert router.answer("soru", allowed_routes=("doc",))["denied"] is True


def test_upload_panel_only_for_admin_and_employee(client):
    login(client, "misafir", "Guclu.Sifre3")
    assert 'action="/upload"' not in client.get("/").get_data(as_text=True)
    client.post("/logout")
    login(client, "mehmet", "Guclu.Sifre2")
    assert 'action="/upload"' in client.get("/").get_data(as_text=True)
