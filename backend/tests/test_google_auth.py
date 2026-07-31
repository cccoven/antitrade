import pytest

import services.google_auth as google_auth


def test_verify_google_id_token_returns_verified_identity(monkeypatch):
    monkeypatch.setattr(
        google_auth,
        "GOOGLE_CLIENT_ID",
        "client.apps.googleusercontent.com",
    )

    def verify(credential, _request, audience):
        assert credential == "valid-token"
        assert audience == "client.apps.googleusercontent.com"
        return {
            "sub": "google-subject",
            "email": "verified@example.com",
            "email_verified": True,
            "name": "Verified User",
        }

    monkeypatch.setattr(google_auth.id_token, "verify_oauth2_token", verify)

    assert google_auth.verify_google_id_token("valid-token") == {
        "sub": "google-subject",
        "email": "verified@example.com",
        "name": "Verified User",
        "hosted_domain": "",
    }


def test_verify_google_id_token_rejects_unverified_email(monkeypatch):
    monkeypatch.setattr(
        google_auth,
        "GOOGLE_CLIENT_ID",
        "client.apps.googleusercontent.com",
    )
    monkeypatch.setattr(
        google_auth.id_token,
        "verify_oauth2_token",
        lambda *_args: {
            "sub": "google-subject",
            "email": "unverified@example.com",
            "email_verified": False,
        },
    )

    with pytest.raises(
        google_auth.GoogleAuthError,
        match="email is not verified",
    ):
        google_auth.verify_google_id_token("valid-token")


def test_verify_google_id_token_requires_configuration(monkeypatch):
    monkeypatch.setattr(google_auth, "GOOGLE_CLIENT_ID", "")

    with pytest.raises(google_auth.GoogleAuthUnavailableError):
        google_auth.verify_google_id_token("token")
