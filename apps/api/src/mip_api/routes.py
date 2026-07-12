import ipaddress
import socket
import uuid
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from mip_api.auth import AuthContext, audit_action, authenticate_request, require_role
from mip_api.config import get_settings
from mip_api.deps import get_db, get_search_service
from mip_api.search import SearchService
from mip_database.models import AlertRule, Source, User
from mip_database.repositories import (
    AlertRepository,
    DocumentRepository,
    EntityRepository,
    EventRepository,
    EvidenceRepository,
    NarrativeRepository,
    SignalRepository,
    SourceRepository,
)
from mip_schemas.api import (
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    SearchRequest,
    SearchResponse,
)
from mip_source_licensing import LicencePolicy, can_serve_full_content, filter_document_body
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/v1")


class AlertCreateRequest(BaseModel):
    user_id: UUID
    name: str = Field(min_length=1, max_length=255)
    entity_ids: list[str] = Field(default_factory=list)
    topic_labels: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    signal_types: list[str] = Field(default_factory=list)
    minimum_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    minimum_score: float = Field(default=0.5, ge=0.0, le=1.0)
    countries: list[str] = Field(default_factory=list)
    delivery_channels: list[str] = Field(default_factory=lambda: ["email"])
    delivery_config: dict[str, Any] = Field(default_factory=dict)
    cooldown_period_seconds: int = Field(default=3600, ge=0)


class AlertUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None
    delivery_channels: list[str] | None = None
    delivery_config: dict[str, Any] | None = None
    cooldown_period_seconds: int | None = Field(default=None, ge=0)


def _error(code: str, message: str, request: Request, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=404 if "NOT_FOUND" in code else 400,
        detail=ErrorResponse(
            error=ErrorDetail(
                code=code,
                message=message,
                details=details or {},
                request_id=getattr(request.state, "request_id", "unknown"),
                trace_id=getattr(request.state, "trace_id", "unknown"),
            )
        ).model_dump(),
    )


def _policy_from_source(source: Source | None) -> LicencePolicy:
    if source is None:
        return LicencePolicy(
            licence_type="unknown",
            redistribution_allowed=False,
            commercial_use_allowed=False,
            quotation_limit=200,
        )
    return LicencePolicy(
        licence_type=source.licence_type,
        redistribution_allowed=source.redistribution_allowed,
        commercial_use_allowed=source.commercial_use_allowed,
        quotation_limit=200 if not source.redistribution_allowed else None,
        attribution_required=source.licence_type == "attribution_required",
    )


def _filter_licensed_text(text: str | None, policy: LicencePolicy) -> str:
    if not text:
        return ""
    return filter_document_body(text, policy)


def _is_public_webhook_url(
    raw_url: str, *, allowed_hosts: set[str], allow_insecure_http: bool
) -> bool:
    parsed = urlparse(raw_url.strip())
    allowed_schemes = {"https"}
    if allow_insecure_http:
        allowed_schemes.add("http")
    if parsed.scheme.lower() not in allowed_schemes or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    if allowed_hosts and hostname not in allowed_hosts:
        return False

    try:
        addr_info = socket.getaddrinfo(
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        return False

    for _, _, _, _, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def _validate_alert_delivery_config(
    delivery_channels: list[str], delivery_config: dict[str, Any]
) -> None:
    if not isinstance(delivery_config, dict):
        raise HTTPException(status_code=400, detail="delivery_config must be an object")

    if "webhook" not in delivery_channels:
        return

    webhook_config = delivery_config.get("webhook")
    webhook_url = webhook_config.get("url") if isinstance(webhook_config, dict) else None
    if not isinstance(webhook_url, str) or not webhook_url.strip():
        raise HTTPException(
            status_code=400, detail="webhook delivery requires delivery_config.webhook.url"
        )

    settings = get_settings()
    allowed_hosts = {
        host.strip().lower()
        for host in settings.alert_webhook_allowed_hosts.split(",")
        if host.strip()
    }
    if settings.app_env != "development" and not allowed_hosts:
        raise HTTPException(
            status_code=400,
            detail="webhook delivery requires ALERT_WEBHOOK_ALLOWED_HOSTS in non-development environments",
        )
    if not _is_public_webhook_url(
        webhook_url,
        allowed_hosts=allowed_hosts,
        allow_insecure_http=settings.app_env == "development",
    ):
        raise HTTPException(
            status_code=400,
            detail="webhook URL must resolve to a public host and use an allowed scheme",
        )


@router.get("/documents")
async def list_documents(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_id: str | None = None,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> PaginatedResponse[dict[str, Any]]:
    repo = DocumentRepository(session)
    source_repo = SourceRepository(session)
    docs, total = await repo.list_documents(page=page, page_size=page_size, source_id=source_id)
    sources = await source_repo.get_by_ids(list({doc.source_id for doc in docs}))
    items = []
    for doc in docs:
        policy = _policy_from_source(sources.get(doc.source_id))
        body = filter_document_body(doc.body, policy) if doc.body else ""
        items.append(
            {
                "document_id": str(doc.document_id),
                "source_id": doc.source_id,
                "title": doc.title,
                "body_preview": body[:500],
                "language": doc.language,
                "published_at": doc.published_at.isoformat() if doc.published_at else None,
                "topic_labels": doc.topic_labels,
            }
        )
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < total,
    )


@router.get("/documents/{document_id}")
async def get_document(
    document_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> dict[str, Any]:
    repo = DocumentRepository(session)
    doc = await repo.get_by_id(document_id)
    if not doc:
        raise _error("DOCUMENT_NOT_FOUND", "The requested document does not exist.", request)
    source_repo = SourceRepository(session)
    source = await source_repo.get_by_id(doc.source_id)
    policy = _policy_from_source(source)
    return {
        "document_id": str(doc.document_id),
        "source_id": doc.source_id,
        "title": doc.title,
        "body": filter_document_body(doc.body, policy),
        "summary": _filter_licensed_text(doc.summary, policy),
        "language": doc.language,
        "published_at": doc.published_at.isoformat() if doc.published_at else None,
        "topic_labels": doc.topic_labels,
        "country_codes": doc.country_codes,
        "canonical_url": doc.canonical_url,
        "full_content_available": can_serve_full_content(policy),
    }


@router.get("/documents/{document_id}/evidence")
async def get_document_evidence(
    document_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> list[dict[str, Any]]:
    doc_repo = DocumentRepository(session)
    doc = await doc_repo.get_by_id(document_id)
    if not doc:
        raise _error("DOCUMENT_NOT_FOUND", "The requested document does not exist.", request)
    source = await SourceRepository(session).get_by_id(doc.source_id)
    policy = _policy_from_source(source)
    evidence_repo = EvidenceRepository(session)
    spans = await evidence_repo.get_by_document(document_id)
    return [
        {
            "evidence_id": str(s.evidence_id),
            "start_offset": s.start_offset,
            "end_offset": s.end_offset,
            "text": _filter_licensed_text(s.text, policy),
            "source_url": s.source_url,
            "confidence": s.confidence,
            "model_version": s.model_version,
        }
        for s in spans
    ]


@router.get("/events")
async def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: str | None = None,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> PaginatedResponse[dict[str, Any]]:
    repo = EventRepository(session)
    events, total = await repo.list_events(page=page, page_size=page_size, event_type=event_type)
    items = [
        {
            "event_id": str(e.event_id),
            "document_id": str(e.document_id),
            "event_type": e.event_type,
            "action": e.action,
            "confidence": e.confidence,
            "event_time": e.event_time.isoformat() if e.event_time else None,
        }
        for e in events
    ]
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size, has_more=page * page_size < total
    )


@router.get("/events/{event_id}")
async def get_event(
    event_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> dict[str, Any]:
    repo = EventRepository(session)
    event = await repo.get_by_id(event_id)
    if not event:
        raise _error("EVENT_NOT_FOUND", "The requested event does not exist.", request)
    return {
        "event_id": str(event.event_id),
        "document_id": str(event.document_id),
        "event_type": event.event_type,
        "action": event.action,
        "object_name": event.object_name,
        "magnitude": event.magnitude,
        "unit": event.unit,
        "confidence": event.confidence,
        "event_time": event.event_time.isoformat() if event.event_time else None,
        "extraction_model_version": event.extraction_model_version,
    }


@router.get("/entities")
async def list_entities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    entity_type: str | None = None,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> PaginatedResponse[dict[str, Any]]:
    repo = EntityRepository(session)
    entities, total = await repo.list_entities(
        page=page, page_size=page_size, entity_type=entity_type
    )
    items = [
        {
            "entity_id": str(e.entity_id),
            "canonical_name": e.canonical_name,
            "entity_type": e.entity_type,
            "country_codes": e.country_codes,
        }
        for e in entities
    ]
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size, has_more=page * page_size < total
    )


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> dict[str, Any]:
    repo = EntityRepository(session)
    entity = await repo.get_by_id(entity_id)
    if not entity:
        raise _error("ENTITY_NOT_FOUND", "The requested entity does not exist.", request)
    return {
        "entity_id": str(entity.entity_id),
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "country_codes": entity.country_codes,
        "external_ids": entity.external_ids,
        "attributes": entity.attributes,
    }


@router.get("/narratives")
async def list_narratives(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> PaginatedResponse[dict[str, Any]]:
    repo = NarrativeRepository(session)
    narratives, total = await repo.list_narratives(page=page, page_size=page_size)
    items = [
        {
            "narrative_id": str(n.narrative_id),
            "title": n.title,
            "lifecycle_state": n.lifecycle_state,
            "velocity_score": n.velocity_score,
            "sentiment_score": n.sentiment_score,
            "last_updated_at": n.last_updated_at.isoformat(),
        }
        for n in narratives
    ]
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size, has_more=page * page_size < total
    )


@router.get("/narratives/{narrative_id}")
async def get_narrative(
    narrative_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> dict[str, Any]:
    repo = NarrativeRepository(session)
    narrative = await repo.get_by_id(narrative_id)
    if not narrative:
        raise _error("NARRATIVE_NOT_FOUND", "The requested narrative does not exist.", request)
    return {
        "narrative_id": str(narrative.narrative_id),
        "title": narrative.title,
        "description": narrative.description,
        "lifecycle_state": narrative.lifecycle_state,
        "topic_labels": narrative.topic_labels,
        "velocity_score": narrative.velocity_score,
        "novelty_score": narrative.novelty_score,
        "source_diversity_score": narrative.source_diversity_score,
        "market_relevance_score": narrative.market_relevance_score,
        "sentiment_score": narrative.sentiment_score,
        "started_at": narrative.started_at.isoformat(),
        "last_updated_at": narrative.last_updated_at.isoformat(),
    }


@router.get("/narratives/{narrative_id}/timeline")
async def get_narrative_timeline(
    narrative_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> list[dict[str, Any]]:
    from mip_database.models import Event, NarrativeEvent

    repo = NarrativeRepository(session)
    narrative = await repo.get_by_id(narrative_id)
    if not narrative:
        raise _error("NARRATIVE_NOT_FOUND", "The requested narrative does not exist.", request)

    from sqlalchemy import select

    result = await session.execute(
        select(Event, NarrativeEvent)
        .join(NarrativeEvent, NarrativeEvent.event_id == Event.event_id)
        .where(NarrativeEvent.narrative_id == narrative_id)
        .order_by(Event.event_time.desc().nullslast())
    )
    timeline = []
    for event, _ in result.all():
        timeline.append(
            {
                "event_id": str(event.event_id),
                "event_type": event.event_type,
                "action": event.action,
                "confidence": event.confidence,
                "event_time": event.event_time.isoformat() if event.event_time else None,
            }
        )
    return timeline


@router.get("/signals/timeseries")
async def get_signals_timeseries(
    signal_type: str | None = None,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> list[dict[str, Any]]:
    repo = SignalRepository(session)
    signals, _ = await repo.list_signals(page=1, page_size=100, signal_type=signal_type)
    return [
        {
            "signal_id": str(s.signal_id),
            "signal_type": s.signal_type,
            "score": s.score,
            "confidence": s.confidence,
            "generated_at": s.generated_at.isoformat(),
            "component_scores": s.component_scores,
        }
        for s in signals
    ]


@router.get("/signals")
async def list_signals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    signal_type: str | None = None,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> PaginatedResponse[dict[str, Any]]:
    repo = SignalRepository(session)
    signals, total = await repo.list_signals(
        page=page, page_size=page_size, signal_type=signal_type
    )
    items = [
        {
            "signal_id": str(s.signal_id),
            "signal_type": s.signal_type,
            "direction": s.direction,
            "score": s.score,
            "confidence": s.confidence,
            "horizon": s.horizon,
            "generated_at": s.generated_at.isoformat(),
            "component_scores": s.component_scores,
        }
        for s in signals
    ]
    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size, has_more=page * page_size < total
    )


@router.get("/signals/{signal_id}")
async def get_signal(
    signal_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> dict[str, Any]:
    repo = SignalRepository(session)
    signal = await repo.get_by_id(signal_id)
    if not signal:
        raise _error("SIGNAL_NOT_FOUND", "The requested signal does not exist.", request)
    return {
        "signal_id": str(signal.signal_id),
        "signal_type": signal.signal_type,
        "direction": signal.direction,
        "score": signal.score,
        "confidence": signal.confidence,
        "horizon": signal.horizon,
        "generated_at": signal.generated_at.isoformat(),
        "expires_at": signal.expires_at.isoformat() if signal.expires_at else None,
        "component_scores": signal.component_scores,
        "calculation_version": signal.calculation_version,
    }


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    search_service: SearchService = Depends(get_search_service),
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> SearchResponse:
    results, total, query_time_ms = await search_service.search(
        body.query,
        filters=body.filters,
        page=body.page,
        page_size=body.page_size,
    )
    source_repo = SourceRepository(session)
    sources = await source_repo.get_by_ids(
        list({r["source_id"] for r in results if r.get("source_id")})
    )
    from mip_schemas.api import SearchResult

    filtered_results = []
    for r in results:
        policy = _policy_from_source(sources.get(r.get("source_id", "")))
        filtered_results.append(
            SearchResult(
                **{
                    **r,
                    "snippet": _filter_licensed_text(r.get("snippet"), policy),
                }
            )
        )
    return SearchResponse(
        results=filtered_results,
        total=total,
        page=body.page,
        page_size=body.page_size,
        query_time_ms=query_time_ms,
    )


@router.post("/alerts")
async def create_alert(
    body: AlertCreateRequest,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_role("admin", "analyst")),
) -> dict[str, Any]:
    user_result = await session.execute(
        select(User).where(
            User.user_id == body.user_id,
            User.tenant_id == auth.tenant_id,
            User.active.is_(True),
        )
    )
    if user_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=400, detail="User does not belong to authenticated tenant")
    _validate_alert_delivery_config(body.delivery_channels, body.delivery_config)

    alert = AlertRule(
        alert_id=uuid.uuid4(),
        tenant_id=auth.tenant_id,
        user_id=body.user_id,
        name=body.name,
        entity_ids=body.entity_ids,
        topic_labels=body.topic_labels,
        event_types=body.event_types,
        signal_types=body.signal_types,
        minimum_confidence=body.minimum_confidence,
        minimum_score=body.minimum_score,
        countries=body.countries,
        delivery_channels=body.delivery_channels,
        delivery_config=body.delivery_config,
        cooldown_period_seconds=body.cooldown_period_seconds,
        active=True,
    )
    repo = AlertRepository(session)
    created = await repo.create(alert)
    await audit_action(
        session,
        tenant_id=auth.tenant_id,
        user_id=None,
        action="alert.create",
        resource_type="alert_rule",
        resource_id=str(created.alert_id),
        details={"name": created.name, "user_id": str(body.user_id)},
    )
    return {"alert_id": str(created.alert_id), "name": created.name, "active": created.active}


@router.get("/alerts")
async def list_alerts(
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(authenticate_request),
) -> list[dict[str, Any]]:
    repo = AlertRepository(session)
    alerts = await repo.list_by_tenant(auth.tenant_id)
    return [
        {
            "alert_id": str(a.alert_id),
            "name": a.name,
            "active": a.active,
            "signal_types": a.signal_types,
            "delivery_channels": a.delivery_channels,
        }
        for a in alerts
    ]


@router.patch("/alerts/{alert_id}")
async def update_alert(
    alert_id: UUID,
    body: AlertUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_role("admin", "analyst")),
) -> dict[str, Any]:
    repo = AlertRepository(session)
    alert = await repo.get_by_id(alert_id)
    if not alert or alert.tenant_id != auth.tenant_id:
        raise _error("ALERT_NOT_FOUND", "The requested alert does not exist.", request)
    payload = body.model_dump(exclude_none=True)
    if "active" in payload:
        alert.active = payload["active"]
    if "name" in payload:
        alert.name = payload["name"]
    if "delivery_channels" in payload:
        alert.delivery_channels = payload["delivery_channels"]
    if "delivery_config" in payload:
        alert.delivery_config = payload["delivery_config"]
    _validate_alert_delivery_config(alert.delivery_channels, alert.delivery_config)
    if "cooldown_period_seconds" in payload:
        alert.cooldown_period_seconds = payload["cooldown_period_seconds"]
    updated = await repo.update(alert)
    await audit_action(
        session,
        tenant_id=auth.tenant_id,
        user_id=None,
        action="alert.update",
        resource_type="alert_rule",
        resource_id=str(updated.alert_id),
        details=payload,
    )
    return {"alert_id": str(updated.alert_id), "name": updated.name, "active": updated.active}


@router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_role("admin", "analyst")),
) -> None:
    repo = AlertRepository(session)
    alert = await repo.get_by_id(alert_id)
    if not alert or alert.tenant_id != auth.tenant_id:
        raise _error("ALERT_NOT_FOUND", "The requested alert does not exist.", request)
    await repo.delete(alert)
    await audit_action(
        session,
        tenant_id=auth.tenant_id,
        user_id=None,
        action="alert.delete",
        resource_type="alert_rule",
        resource_id=str(alert_id),
    )
