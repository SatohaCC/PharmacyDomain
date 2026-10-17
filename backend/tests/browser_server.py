"""ブラウザー結合テスト専用のJWT検証付き起動点。本番では起動しない。"""

import json
import os
from pathlib import Path

from app.bootstrap import create_app
from app.presentational.oidc import OidcSettings, OidcVerifiedSubjectProvider
from tests.factories.oidc_factory import issue_token, signing_key
from tests.fakes.signing_key_resolver import StubSigningKeyResolver

_provider = OidcVerifiedSubjectProvider(
    OidcSettings(
        issuer="seed",
        audience="pharmacydomain",
        jwks_url="https://idp.example.test/jwks",
    ),
    StubSigningKeyResolver(signing_key()),
)
app = create_app(identity_provider=_provider)
Path(os.environ["REAL_E2E_TOKENS"]).write_text(
    json.dumps(
        {
            "vendor": issue_token(
                issuer="seed", audience="pharmacydomain", subject="vendor-admin"
            ),
            "invitee": issue_token(
                issuer="seed", audience="pharmacydomain", subject="browser-invitee"
            ),
        }
    ),
    encoding="utf-8",
)
