from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from urllib.parse import urlencode
from pydantic import BaseModel, Field
import uuid
import structlog

logger = structlog.get_logger()


class SMARTConfig(BaseModel):
    client_id: str
    client_secret: Optional[str] = None
    token_uri: str
    authorization_uri: str
    scope: str = "patient/*.read launch/patient"
    launch_uri: str = "/smart/launch"
    redirect_uri: str = "/smart/callback"
    jwks_uri: Optional[str] = None
    issuer: str = "http://localhost:8080/fhir"
    audience: str = "http://localhost:8080/fhir"
    fhir_base_url: str = "http://localhost:8080/fhir"


class SMARTState(BaseModel):
    state: str
    client_id: str
    redirect_uri: str
    scope: str
    nonce: str
    code_challenge: Optional[str] = None
    code_challenge_method: Optional[str] = None
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SMARTTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str
    patient: Optional[str] = None
    id_token: Optional[str] = None
    refresh_token: Optional[str] = None


class SMARTLaunchContext(BaseModel):
    patient_id: str
    practitioner_id: Optional[str] = None
    encounter_id: Optional[str] = None
    user_role: str = "patient"
    fhir_server_base: str
    launch_id: str
    scopes: List[str] = []


class SMARTLaunchRequest(BaseModel):
    launch_uri: Optional[str] = None
    fhir_server_base: Optional[str] = None


class SMARTAuthorizeRequest(BaseModel):
    response_type: str = "code"
    client_id: str
    redirect_uri: str
    scope: str = "patient/*.read launch/patient"
    state: str
    code_challenge: Optional[str] = None
    code_challenge_method: Optional[str] = None
    launch: Optional[str] = None


class SMARTBundleRequest(BaseModel):
    grant_type: str = "authorization_code"
    code: str
    redirect_uri: str
    client_id: str
    client_secret: Optional[str] = None
    code_verifier: Optional[str] = None


class SMARTService:
    def __init__(self, config: SMARTConfig):
        self.config = config
        self._pending_states: Dict[str, SMARTState] = {}
        self._authorization_codes: Dict[str, Dict[str, Any]] = {}
        self._access_tokens: Dict[str, Dict[str, Any]] = {}
        self._pkce_challenges: Dict[str, str] = {}

    def build_launch_url(self, launch_request: Optional[SMARTLaunchRequest] = None) -> str:
        state = uuid.uuid4().hex
        nonce = uuid.uuid4().hex
        redirect = self.config.redirect_uri

        state_data = SMARTState(
            state=state,
            client_id=self.config.client_id,
            redirect_uri=redirect,
            scope=self.config.scope,
            nonce=nonce,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        self._pending_states[state] = state_data

        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "redirect_uri": redirect,
            "scope": self.config.scope,
            "state": state,
            "nonce": nonce,
            "aud": self.config.fhir_base_url,
        }

        return f"{self.config.authorization_uri}?{urlencode(params)}"

    async def authorize(
        self,
        request: SMARTAuthorizeRequest,
    ) -> Dict[str, Any]:
        if request.client_id != self.config.client_id:
            raise ValueError("Invalid client_id")

        if request.state not in self._pending_states:
            raise ValueError("Invalid or expired state parameter")

        state_data = self._pending_states.pop(request.state)
        if state_data.expires_at < datetime.utcnow():
            raise ValueError("Authorization request expired")

        code = uuid.uuid4().hex
        self._authorization_codes[code] = {
            "client_id": request.client_id,
            "redirect_uri": request.redirect_uri,
            "scope": request.scope or state_data.scope,
            "nonce": state_data.nonce,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=10),
            "code_challenge": request.code_challenge,
            "code_challenge_method": request.code_challenge_method,
        }

        redirect_params = {"code": code, "state": request.state}
        redirect_url = f"{request.redirect_uri}?{urlencode(redirect_params)}"

        logger.info("smart_authorization_issued", code=code[:8], client_id=request.client_id)
        return {"redirect_url": redirect_url, "code": code}

    async def token_exchange(
        self,
        request: SMARTBundleRequest,
    ) -> SMARTTokenResponse:
        if request.code not in self._authorization_codes:
            raise ValueError("Invalid authorization code")

        code_data = self._authorization_codes.pop(request.code)
        if code_data["expires_at"] < datetime.utcnow():
            raise ValueError("Authorization code expired")

        if request.client_id != code_data["client_id"]:
            raise ValueError("client_id mismatch")

        if request.client_secret and request.client_secret != self.config.client_secret:
            raise ValueError("Invalid client_secret")

        access_token = uuid.uuid4().hex
        refresh_token = uuid.uuid4().hex
        expires_in = 3600

        self._access_tokens[access_token] = {
            "client_id": request.client_id,
            "scope": code_data["scope"],
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(seconds=expires_in),
            "refresh_token": refresh_token,
            "nonce": code_data["nonce"],
        }

        launch_context: Optional[SMARTLaunchContext] = None
        patient_id = None
        scopes = code_data["scope"].split()

        if "launch/patient" in scopes:
            patient_id = f"patient-{uuid.uuid4().hex[:8]}"

        logger.info("smart_token_issued", access_token=access_token[:8], client_id=request.client_id)

        return SMARTTokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=expires_in,
            scope=code_data["scope"],
            patient=patient_id,
        )

    async def introspect_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        token_data = self._access_tokens.get(access_token)
        if not token_data:
            return None

        if token_data["expires_at"] < datetime.utcnow():
            del self._access_tokens[access_token]
            return None

        return {
            "active": True,
            "client_id": token_data["client_id"],
            "scope": token_data["scope"],
            "exp": int(token_data["expires_at"].timestamp()),
        }

    async def refresh_token_exchange(self, refresh_token: str) -> SMARTTokenResponse:
        for token_key, token_data in list(self._access_tokens.items()):
            if token_data.get("refresh_token") == refresh_token:
                if token_data["expires_at"] < datetime.utcnow() - timedelta(days=7):
                    del self._access_tokens[token_key]
                    raise ValueError("Refresh token expired")

                new_access = uuid.uuid4().hex
                new_refresh = uuid.uuid4().hex
                expires_in = 3600

                token_data["access_token"] = new_access
                token_data["refresh_token"] = new_refresh
                token_data["created_at"] = datetime.utcnow()
                token_data["expires_at"] = datetime.utcnow() + timedelta(seconds=expires_in)

                return SMARTTokenResponse(
                    access_token=new_access,
                    token_type="Bearer",
                    expires_in=expires_in,
                    scope=token_data["scope"],
                    refresh_token=new_refresh,
                )

        raise ValueError("Invalid refresh token")

    def get_launch_context(self, access_token: str) -> Optional[SMARTLaunchContext]:
        token_data = self._access_tokens.get(access_token)
        if not token_data:
            return None

        scopes = token_data["scope"].split()

        return SMARTLaunchContext(
            patient_id=f"patient-{uuid.uuid4().hex[:8]}",
            fhir_server_base=self.config.fhir_base_url,
            launch_id=uuid.uuid4().hex,
            scopes=scopes,
        )


smart_config = SMARTConfig(
    client_id="codeblue-smart-client",
    client_secret="codeblue-smart-secret-change-in-prod",
    token_uri="http://localhost:8000/smart/token",
    authorization_uri="http://localhost:8000/smart/authorize",
    scope="patient/*.read launch/patient user/*.read openid fhirUser",
    fhir_base_url="http://localhost:8080/fhir",
)

smart_service = SMARTService(smart_config)
