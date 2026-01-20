from __future__ import annotations

import hashlib
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone

from .models import PageView, Post


def _ensure_session_key(request: HttpRequest) -> str:
    # Garante que existe session_key para estimar "visitantes únicos" sem IP.
    if request.session.session_key:
        return request.session.session_key
    request.session.create()
    return request.session.session_key or ""


def get_session_hash(request: HttpRequest) -> str:
    key = _ensure_session_key(request)
    if not key:
        return ""
    salt = getattr(settings, "SECRET_KEY", "")
    return hashlib.sha256((salt + ":" + key).encode("utf-8")).hexdigest()


def get_referrer(request: HttpRequest) -> str:
    return (request.META.get("HTTP_REFERER") or "")[:500]


def get_ref_domain(referrer: str) -> str:
    try:
        return (urlparse(referrer).netloc or "")[:255]
    except Exception:
        return ""


def get_user_agent(request: HttpRequest) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:255]


def classify_source(referrer: str, utm_source: str) -> str:
    if utm_source:
        return "utm"
    if not referrer:
        return "direct"

    host = (get_ref_domain(referrer) or "").lower()
    if any(x in host for x in ("google.", "bing.", "yahoo.", "duckduckgo.")):
        return "search"
    if any(x in host for x in ("facebook.", "instagram.", "t.co", "twitter.", "linkedin.", "tiktok.", "youtube.")):
        return "social"
    return "referral"


def record_post_view(request: HttpRequest, post: Post) -> None:
    if request.method != "GET":
        return
    ref = get_referrer(request)
    utm_source = (request.GET.get("utm_source") or "")[:100]
    utm_medium = (request.GET.get("utm_medium") or "")[:100]
    utm_campaign = (request.GET.get("utm_campaign") or "")[:150]

    PageView.objects.create(
        created_at=timezone.now(),
        kind="post",
        post=post,
        author=post.author,
        category=post.category,
        session_hash=get_session_hash(request),
        referrer=ref,
        ref_domain=get_ref_domain(ref),
        user_agent=get_user_agent(request),
        source_type=classify_source(ref, utm_source),
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
    )


def is_safe_http_url(url: str) -> bool:
    try:
        p = urlparse(url)
    except Exception:
        return False
    return p.scheme in {"http", "https"} and bool(p.netloc)
