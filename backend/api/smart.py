from fastapi import APIRouter, Depends, Query
from typing import Dict, Any, Optional

from backend.services.auth import get_current_user, TokenPayload
from backend.services.security import rbac_service, Permission

router = APIRouter(prefix="/smart", tags=["smart-on-fhir"])


@router.get("/launch")
async def smart_launch():
    from backend.services.smart_on_fhir import smart_service
    url = smart_service.build_launch_url()
    return {"authorization_url": url, "instructions": "Redirect browser to authorization_url"}


@router.get("/authorize")
async def smart_authorize(
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query(...),
    state: str = Query(...),
    nonce: Optional[str] = Query(None),
    aud: Optional[str] = Query(None),
    code_challenge: Optional[str] = Query(None),
    code_challenge_method: Optional[str] = Query(None),
    launch: Optional[str] = Query(None),
):
    from backend.services.smart_on_fhir import smart_service, SMARTAuthorizeRequest

    request = SMARTAuthorizeRequest(
        response_type=response_type,
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        state=state,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        launch=launch,
    )

    result = await smart_service.authorize(request)
    return {"redirect_url": result["redirect_url"]}


@router.post("/token")
async def smart_token(
    grant_type: str = Query(...),
    code: Optional[str] = Query(None),
    redirect_uri: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    client_secret: Optional[str] = Query(None),
    refresh_token: Optional[str] = Query(None),
    code_verifier: Optional[str] = Query(None),
):
    from backend.services.smart_on_fhir import smart_service, SMARTBundleRequest

    if grant_type == "authorization_code":
        request = SMARTBundleRequest(
            grant_type=grant_type,
            code=code or "",
            redirect_uri=redirect_uri or "",
            client_id=client_id or "",
            client_secret=client_secret,
            code_verifier=code_verifier,
        )
        token = await smart_service.token_exchange(request)
        return token.model_dump()

    elif grant_type == "refresh_token":
        token = await smart_service.refresh_token_exchange(refresh_token or "")
        return token.model_dump()

    else:
        return {"error": "unsupported_grant_type"}


@router.get("/patient-context")
async def get_patient_context(user: TokenPayload = Depends(get_current_user)):
    from backend.services.smart_on_fhir import smart_service

    token = user.sub
    context = smart_service.get_launch_context(token)

    if not context:
        return {
            "patient_id": None,
            "message": "No active SMART launch context. Complete SMART authorization first."
        }

    return {
        "patient_id": context.patient_id,
        "encounter_id": context.encounter_id,
        "fhir_server_base": context.fhir_server_base,
        "scopes": context.scopes,
        "launch_id": context.launch_id,
    }
