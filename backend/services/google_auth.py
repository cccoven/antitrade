"""Google Identity Services ID token verification."""

from google.auth.exceptions import GoogleAuthError as GoogleLibraryAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from config import GOOGLE_CLIENT_ID


class GoogleAuthError(ValueError):
    pass


class GoogleAuthUnavailableError(GoogleAuthError):
    pass


def verify_google_id_token(credential: str) -> dict[str, str]:
    if not GOOGLE_CLIENT_ID:
        raise GoogleAuthUnavailableError("Google login is not configured")
    if not credential.strip():
        raise GoogleAuthError("Invalid Google credential")

    try:
        claims = id_token.verify_oauth2_token(
            credential,
            Request(),
            GOOGLE_CLIENT_ID,
        )
    except (ValueError, GoogleLibraryAuthError) as exc:
        raise GoogleAuthError("Invalid Google credential") from exc

    subject = claims.get("sub")
    email = claims.get("email")
    if (
        not isinstance(subject, str)
        or not subject
        or not isinstance(email, str)
        or not email
        or claims.get("email_verified") is not True
    ):
        raise GoogleAuthError("Google account email is not verified")

    name = claims.get("name")
    hosted_domain = claims.get("hd")
    return {
        "sub": subject,
        "email": email,
        "name": name if isinstance(name, str) else "",
        "hosted_domain": hosted_domain if isinstance(hosted_domain, str) else "",
    }
