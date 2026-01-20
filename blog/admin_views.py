from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db.models import Count
from django.db.models import Avg, Max
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from django.contrib import admin

from .models import EngagementEvent, LinkClick, PageView, Post


@dataclass(frozen=True)
class DateRange:
    start: datetime  # inclusive
    end: datetime  # exclusive


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def _make_range(request: HttpRequest) -> tuple[DateRange, str, date | None, date | None]:
    tz = timezone.get_current_timezone()
    today = timezone.localdate()

    preset = (request.GET.get("preset") or "7d").lower()
    start_d = _parse_date(request.GET.get("start"))
    end_d = _parse_date(request.GET.get("end"))

    if preset == "today":
        start_d = today
        end_d = today
    elif preset == "7d":
        start_d = today - timedelta(days=6)
        end_d = today
    elif preset == "30d":
        start_d = today - timedelta(days=29)
        end_d = today
    elif preset == "custom":
        # usa start/end da query
        if not start_d:
            start_d = today - timedelta(days=6)
        if not end_d:
            end_d = today
    else:
        preset = "7d"
        start_d = today - timedelta(days=6)
        end_d = today

    # end exclusivo: +1 dia
    start_dt = timezone.make_aware(datetime.combine(start_d, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(end_d + timedelta(days=1), datetime.min.time()), tz)
    return DateRange(start=start_dt, end=end_dt), preset, start_d, end_d


def oxira_dashboard(request: HttpRequest) -> HttpResponse:
    dr, preset, start_d, end_d = _make_range(request)

    views_qs = PageView.objects.filter(created_at__gte=dr.start, created_at__lt=dr.end)
    clicks_qs = LinkClick.objects.filter(created_at__gte=dr.start, created_at__lt=dr.end)
    engage_qs = EngagementEvent.objects.filter(created_at__gte=dr.start, created_at__lt=dr.end)

    total_views = views_qs.count()
    unique_views = views_qs.exclude(session_hash="").values("session_hash").distinct().count()
    total_clicks = clicks_qs.count()
    ctr = ((total_clicks / total_views) * 100.0) if total_views else 0.0

    today = timezone.localdate()
    today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()), timezone.get_current_timezone())
    tomorrow_start = today_start + timedelta(days=1)

    views_today = PageView.objects.filter(created_at__gte=today_start, created_at__lt=tomorrow_start).count()
    clicks_today = LinkClick.objects.filter(created_at__gte=today_start, created_at__lt=tomorrow_start).count()
    posts_published_today = Post.objects.filter(status="published", published_date__date=today).count()

    # Engajamento (tempo/scroll)
    time_max = (
        engage_qs.filter(event="time")
        .exclude(session_hash="")
        .values("post_id", "session_hash")
        .annotate(max_time=Max("value_int"))
    )
    scroll_max = (
        engage_qs.filter(event="scroll")
        .exclude(session_hash="")
        .values("post_id", "session_hash")
        .annotate(max_scroll=Max("value_int"))
    )

    avg_time_seconds = time_max.aggregate(avg=Avg("max_time")).get("avg") or 0.0
    avg_scroll_percent = scroll_max.aggregate(avg=Avg("max_scroll")).get("avg") or 0.0

    view_sessions = (
        views_qs.filter(kind="post")
        .exclude(session_hash="")
        .values("session_hash")
        .distinct()
        .count()
    )
    deep_sessions = (
        scroll_max.filter(max_scroll__gte=75)
        .values("session_hash")
        .distinct()
        .count()
    )
    read_rate = ((deep_sessions / view_sessions) * 100.0) if view_sessions else 0.0

    # Origens (por tipo)
    sources = (
        views_qs.values("source_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    top_ref_domains = (
        views_qs.exclude(ref_domain="")
        .values("ref_domain")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )

    top_utm = (
        views_qs.exclude(utm_source="")
        .values("utm_source", "utm_medium", "utm_campaign")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )

    # Ranking: posts mais vistos no período
    top_posts = (
        views_qs.filter(kind="post", post__isnull=False)
        .values("post_id", "post__title", "post__slug", "post__author__username", "post__author__first_name", "post__author__last_name")
        .annotate(views=Count("id"), uniques=Count("session_hash", distinct=True))
        .order_by("-views")[:20]
    )

    # Cliques por post no período
    clicks_by_post = {
        row["post_id"]: row["clicks"]
        for row in clicks_qs.filter(post__isnull=False)
        .values("post_id")
        .annotate(clicks=Count("id"))
    }

    top_posts_enriched = []
    for row in top_posts:
        pid = row["post_id"]
        v = int(row["views"] or 0)
        c = int(clicks_by_post.get(pid, 0) or 0)
        top_posts_enriched.append(
            {
                **row,
                "clicks": c,
                "ctr": ((c / v) * 100.0) if v else 0.0,
            }
        )

    # Autores que mais publicaram no período (por published_date)
    top_authors = (
        Post.objects.filter(status="published", published_date__gte=dr.start, published_date__lt=dr.end)
        .values("author__username", "author__first_name", "author__last_name")
        .annotate(posts=Count("id"))
        .order_by("-posts")[:20]
    )

    # Série diária: views e clicks
    views_series = (
        views_qs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    clicks_series = (
        clicks_qs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    # Top links externos
    top_links = (
        clicks_qs.values("url")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:20]
    )

    context = {
        **admin.site.each_context(request),
        "preset": preset,
        "start": start_d,
        "end": end_d,
        "total_views": total_views,
        "unique_views": unique_views,
        "total_clicks": total_clicks,
        "ctr": ctr,
        "views_today": views_today,
        "clicks_today": clicks_today,
        "posts_published_today": posts_published_today,
        "avg_time_seconds": avg_time_seconds,
        "avg_scroll_percent": avg_scroll_percent,
        "read_rate": read_rate,
        "sources": list(sources),
        "top_ref_domains": top_ref_domains,
        "top_utm": top_utm,
        "top_posts": top_posts_enriched,
        "top_authors": top_authors,
        "views_series": list(views_series),
        "clicks_series": list(clicks_series),
        "top_links": top_links,
        "range_label": f"{start_d.strftime('%d/%m/%Y')} – {end_d.strftime('%d/%m/%Y')}",
    }

    return render(request, "admin/oxira_dashboard.html", context)
