import logging

from dataclasses import dataclass
from typing import List
from typing import Optional
from typing import Set
from typing import TypedDict

import requests

from jose import jwt
from requests.auth import HTTPBasicAuth

from ping_identity_auth_playground.support.http_utils import build_url_with_query_strings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OIDCConfigurationDocument:
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    issuer: str
    scopes_supported: List[str]
    response_types_supported: List[str]
    subject_types_supported: List[str]
    id_token_signing_alg_values_supported: List[str]
    token_endpoint_auth_methods_supported: List[str]
    backchannel_authentication_endpoint: Optional[str] = None
    pushed_authorization_request_endpoint: Optional[str] = None
    end_session_endpoint: Optional[str] = None
    registration_endpoint: Optional[str] = None
    introspection_endpoint: Optional[str] = None
    device_authorization_endpoint: Optional[str] = None
    mfa_challenge_endpoint: Optional[str] = None
    revocation_endpoint: Optional[str] = None
    backchannel_token_delivery_modes_supported: Optional[List[str]] = None
    code_challenge_methods_supported: Optional[List[str]] = None
    request_object_signing_alg_values_supported: Optional[List[str]] = None
    request_object_encryption_alg_values_supported: Optional[List[str]] = None
    backchannel_authentication_request_signing_alg_values_supported: Optional[List[str]] = None
    request_object_encryption_enc_values_supported: Optional[List[str]] = None
    id_token_encryption_enc_values_supported: Optional[List[str]] = None
    id_token_encryption_alg_values_supported: Optional[List[str]] = None
    code_challenge_methods_supported: Optional[List[str]] = None
    response_modes_supported: Optional[List[str]] = None
    grant_types_supported: Optional[List[str]] = None
    userinfo_signing_alg_values_supported: Optional[List[str]] = None
    claim_types_supported: Optional[List[str]] = None
    claims_supported: Optional[List[str]] = None
    token_endpoint_auth_signing_alg_values_supported: Optional[List[str]] = None
    claims_parameter_supported: Optional[bool] = None
    request_uri_parameter_supported: Optional[bool] = None
    request_parameter_supported: Optional[bool] = None
    require_pushed_authorization_requests: Optional[bool] = None
    backchannel_user_code_parameter_supported: Optional[bool] = None
    ping_revoked_sris_endpoint: Optional[str] = None
    ping_session_management_sris_endpoint: Optional[str] = None
    ping_session_management_users_endpoint: Optional[str] = None
    ping_end_session_endpoint: Optional[str] = None


class JWTPublicKey(TypedDict):
    alg: str
    e: str
    kid: str
    kty: str
    n: str
    use: str
    x5t: Optional[str]
    x5c: Optional[str]


class JWTPublicKeys(TypedDict):
    keys: List[JWTPublicKey]


class OIDCProvider:
    oidc_configuration_document: OIDCConfigurationDocument
    jwt_public_keys: JWTPublicKeys
    jwt_public_keys_algorithms: Set[str]

    domain = str
    app_client_key = str
    app_client_secret = str
    scopes = str

    @classmethod
    def configure_class_properties(cls, domain, app_key, app_secret, scopes: List[str]):
        cls.domain = domain
        cls.app_client_key = app_key
        cls.app_client_secret = app_secret
        cls.scopes = scopes

    @classmethod
    def configure_oidc_configuration_document(cls):
        document = requests.get(f"https://{cls.domain}/.well-known/openid-configuration", verify=False).json()

        # First let's configure the OIDC configuration document
        cls.oidc_configuration_document = OIDCConfigurationDocument(**document)

        # Now the public keys to verify the JWT created by the Authorization Server
        public_keys = requests.get(cls.oidc_configuration_document.jwks_uri, verify=False).json()

        jwt_public_keys_algorithms = set()
        for public_key in public_keys["keys"]:
            algorithm = public_key.get("alg")
            if algorithm:
                jwt_public_keys_algorithms.add(algorithm)

        cls.jwt_public_keys = public_keys
        cls.jwt_public_keys_algorithms = jwt_public_keys_algorithms

    @classmethod
    def build_authorization_url(cls, redirect_uri: str, state: str):
        auth_url = cls.oidc_configuration_document.authorization_endpoint
        params = {
            "state": state,
            "client_id": cls.app_client_key,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(cls.scopes),
        }
        logger.debug("Building authorization URL...")
        return build_url_with_query_strings(auth_url, params)

    @classmethod
    def acquire_token_by_auth_code_flow(cls, code: str, redirect_uri: str):
        token_endpoint = cls.oidc_configuration_document.token_endpoint
        app_credentials = HTTPBasicAuth(cls.app_client_key, cls.app_client_secret)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": cls.app_client_key,
            "redirect_uri": redirect_uri,
            "scope": " ".join(cls.scopes),
        }
        response = requests.post(token_endpoint, headers=headers, data=body, auth=app_credentials, verify=False)
        content = response.json()
        id_token = content["id_token"]
        access_token = content["access_token"]
        claims = cls._retrieve_claims(id_token, access_token)
        return content, claims

    @classmethod
    def _retrieve_claims(cls, id_token: str, access_token: str) -> dict:
        issuer = cls.oidc_configuration_document.issuer
        algorithms = list(cls.jwt_public_keys_algorithms)
        if not algorithms:
            algorithms.append(jwt.get_unverified_headers(id_token)["alg"])
        audience = cls.app_client_key
        public_keys = cls.jwt_public_keys

        return jwt.decode(
            id_token, public_keys, algorithms=algorithms, audience=audience, issuer=issuer, access_token=access_token
        )

    @classmethod
    def build_logout_url(cls, return_to):
        base_endpoint = cls.oidc_configuration_document.token_endpoint.split("/oauth2/token")[0]
        logout_endpoint = f"{base_endpoint}/logout"
        params = {
            "logout_uri": return_to,
            "client_id": cls.app_client_key,
        }
        logger.debug("Building logout URL...")
        return build_url_with_query_strings(logout_endpoint, params)

    @classmethod
    def get_user_info(cls, access_token: str):
        userinfo_endpoint = cls.oidc_configuration_document.userinfo_endpoint
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        result = requests.get(userinfo_endpoint, headers=headers, verify=False)
        body = result.json()
        return body
