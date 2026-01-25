from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpRequest
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
from datetime import timedelta, datetime
import hashlib

from .forms import AuthorSignupForm
from .metrics import get_session_hash, is_safe_http_url, record_post_view
from .models import Category, EngagementEvent, LinkClick, Post, UserProfile

def post_list(request):
    posts = Post.objects.filter(status='published').order_by('-published_date')
    return render(request, 'blog/post_list.html', {'posts': posts})

def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, status='published')

    # Métrica: view do post
    record_post_view(request, post)

    try:
        author_profile = post.author.profile
    except UserProfile.DoesNotExist:
        author_profile = None

    more_from_author = (
        Post.objects.filter(status='published', author=post.author)
        .exclude(pk=post.pk)
        .order_by('-published_date')[:5]
    )
    return render(
        request,
        'blog/post_detail.html',
        {'post': post, 'author_profile': author_profile, 'more_from_author': more_from_author},
    )


@staff_member_required
def post_preview(request, pk: int):
    post = get_object_or_404(Post.objects.select_related('author'), pk=pk)

    try:
        author_profile = post.author.profile
    except UserProfile.DoesNotExist:
        author_profile = None

    more_from_author = (
        Post.objects.filter(status='published', author=post.author)
        .exclude(pk=post.pk)
        .order_by('-published_date')[:5]
    )

    return render(
        request,
        'blog/post_detail.html',
        {
            'post': post,
            'author_profile': author_profile,
            'more_from_author': more_from_author,
            'preview_mode': True,
        },
    )


@csrf_exempt
@require_POST
def metrics_link_click(request: HttpRequest):
    # Proteção simples contra POSTs externos
    host = (request.get_host() or '').lower()
    origin = (request.headers.get('Origin') or '').lower()
    ref = (request.headers.get('Referer') or '').lower()
    if origin and host not in origin:
        return JsonResponse({'ok': False}, status=400)
    if ref and host not in ref:
        return JsonResponse({'ok': False}, status=400)

    url = (request.POST.get('url') or '').strip()
    if not url or len(url) > 1000 or not is_safe_http_url(url):
        return JsonResponse({'ok': False}, status=400)

    post_id = request.POST.get('post_id')
    post = None
    if post_id and str(post_id).isdigit():
        post = Post.objects.filter(pk=int(post_id)).only('id').first()

    LinkClick.objects.create(
        post=post,
        url=url,
        session_hash=get_session_hash(request),
    )
    return JsonResponse({'ok': True})


@csrf_exempt
@require_POST
def metrics_engagement(request: HttpRequest):
    host = (request.get_host() or '').lower()
    origin = (request.headers.get('Origin') or '').lower()
    ref = (request.headers.get('Referer') or '').lower()
    if origin and host not in origin:
        return JsonResponse({'ok': False}, status=400)
    if ref and host not in ref:
        return JsonResponse({'ok': False}, status=400)

    event = (request.POST.get('event') or '').strip().lower()
    if event not in {'time', 'scroll'}:
        return JsonResponse({'ok': False}, status=400)

    value = request.POST.get('value')
    try:
        value_int = int(value)
    except Exception:
        return JsonResponse({'ok': False}, status=400)

    # limites
    if event == 'time':
        value_int = max(0, min(600, value_int))
    else:
        value_int = max(0, min(100, value_int))

    post_id = request.POST.get('post_id')
    post = None
    if post_id and str(post_id).isdigit():
        post = Post.objects.filter(pk=int(post_id)).only('id').first()

    EngagementEvent.objects.create(
        post=post,
        event=event,
        value_int=value_int,
        session_hash=get_session_hash(request),
    )
    return JsonResponse({'ok': True})

def category_list(request, slug):
    category = get_object_or_404(Category, slug=slug)
    posts = Post.objects.filter(status='published', category=category).order_by('-published_date')
    return render(request, 'blog/post_list.html', {'posts': posts, 'category': category})


def author_detail(request, username):
    User = get_user_model()
    author = get_object_or_404(User.objects.select_related('profile'), username=username)

    try:
        profile = author.profile
    except UserProfile.DoesNotExist:
        profile = None

    posts_qs = Post.objects.filter(status='published', author=author).order_by('-published_date')
    posts_count = posts_qs.count()
    paginator = Paginator(posts_qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    role_label = 'Autor'
    if profile and getattr(profile, 'role', None) == 'author':
        role_label = 'Repórter'
    elif profile and getattr(profile, 'role', None) == 'admin':
        role_label = 'Editor'

    return render(
        request,
        'blog/author_detail.html',
        {
            'author': author,
            'profile': profile,
            'role_label': role_label,
            'page_obj': page_obj,
            'posts': page_obj.object_list,
            'posts_count': posts_count,
        },
    )


@transaction.atomic
def author_signup(request: HttpRequest):
    if request.method != 'POST':
        return redirect('admin:login')

    form = AuthorSignupForm(request.POST, request.FILES)
    if not form.is_valid():
        # Re-render a tela de login do admin, já com erros do cadastro
        from django.contrib.auth.forms import AuthenticationForm

        login_form = AuthenticationForm(request)
        return render(request, 'admin/login.html', {'form': login_form, 'signup_form': form})

    user = form.save(commit=False)
    user.email = form.cleaned_data['email']
    user.first_name = form.cleaned_data['first_name']
    user.last_name = form.cleaned_data.get('last_name') or ''
    user.is_active = False
    user.is_staff = False
    user.is_superuser = False
    user.save()
    form.save_m2m()

    profile = user.profile
    profile.role = 'author'
    profile.cpf = form.cleaned_data.get('cpf')
    profile.phone = form.cleaned_data.get('phone')
    profile.instagram = form.cleaned_data.get('instagram')
    profile.bio = form.cleaned_data.get('bio')
    avatar = form.cleaned_data.get('avatar')
    if avatar:
        profile.avatar = avatar
    profile.save()

    messages.success(request, 'Cadastro enviado para aprovação. Assim que for aprovado, você poderá acessar o painel.')
    return redirect('admin:login')


def consultas(request: HttpRequest):
    return render(request, 'blog/consultas.html')


def _http_get_json(url: str, timeout: float = 8.0):
    req = Request(
        url,
        headers={
            'User-Agent': 'Oxira/1.0 (+https://oxira.local)',
            'Accept': 'application/json',
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
    return json.loads(raw)


def _cached_fetch_json(cache_key: str, url: str, ttl_seconds: int):
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    data = _http_get_json(url)
    cache.set(cache_key, data, ttl_seconds)
    return data


def _norm_ccy(value: str) -> str | None:
    value = (value or '').strip().upper()
    if len(value) != 3:
        return None
    if not value.isalpha():
        return None
    return value


@require_GET
def api_consultas_fx_latest(request: HttpRequest):
    base = _norm_ccy(request.GET.get('base')) or 'USD'
    symbols_raw = (request.GET.get('symbols') or '').strip()
    symbols = []
    if symbols_raw:
        for part in symbols_raw.split(','):
            c = _norm_ccy(part)
            if c:
                symbols.append(c)

    # limite simples
    symbols = symbols[:10]

    url = f"https://api.frankfurter.app/latest?from={base}"
    if symbols:
        url += "&to=" + ",".join(symbols)

    cache_key = f"consultas:fx:latest:{base}:{','.join(symbols) if symbols else 'ALL'}"
    try:
        data = _cached_fetch_json(cache_key, url, ttl_seconds=600)
        return JsonResponse(data, json_dumps_params={'ensure_ascii': False})
    except (HTTPError, URLError, TimeoutError, ValueError) as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=502, json_dumps_params={'ensure_ascii': False})


@require_GET
def api_consultas_fx_range(request: HttpRequest):
    base = _norm_ccy(request.GET.get('base')) or 'USD'

    days_raw = (request.GET.get('days') or '').strip()
    try:
        days = int(days_raw) if days_raw else 30
    except Exception:
        days = 30

    days = max(7, min(60, days))

    end = timezone.localdate()
    start = end - timedelta(days=days - 1)

    # Frankfurter: /YYYY-MM-DD..YYYY-MM-DD?from=USD&to=BRL
    url = f"https://api.frankfurter.app/{start.isoformat()}..{end.isoformat()}?from={base}&to=BRL"
    cache_key = f"consultas:fx:range:{base}:{days}:{end.isoformat()}"

    try:
        data = _cached_fetch_json(cache_key, url, ttl_seconds=600)
        rates = data.get('rates') if isinstance(data, dict) else None
        series = []
        if isinstance(rates, dict):
            for d, v in rates.items():
                if isinstance(v, dict) and isinstance(v.get('BRL'), (int, float)):
                    series.append({'date': d, 'rate': float(v['BRL'])})

        series.sort(key=lambda x: x['date'])
        current = series[-1] if series else None

        return JsonResponse(
            {
                'ok': True,
                'base': base,
                'days': days,
                'series': series,
                'current': current,
            },
            json_dumps_params={'ensure_ascii': False},
        )
    except (HTTPError, URLError, TimeoutError, ValueError) as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=502, json_dumps_params={'ensure_ascii': False})


@require_GET
@require_GET
def api_consultas_crypto_prices(request: HttpRequest):
    # CoinGecko (sem chave), com cache para reduzir rate-limit.
    # Aceita seleção via querystring, mas só por whitelist (segurança + estabilidade).
    allowed_ids = {
        'bitcoin',
        'ethereum',
        'solana',
        'ripple',
        'cardano',
        'dogecoin',
    }

    ids_raw = (request.GET.get('ids') or '').strip().lower()
    requested = []
    if ids_raw:
        for part in ids_raw.split(','):
            p = (part or '').strip().lower()
            if p in allowed_ids and p not in requested:
                requested.append(p)

    if not requested:
        requested = ['bitcoin', 'ethereum']

    # limite
    requested = requested[:10]

    ids_param = ','.join(requested)
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids_param}"
        "&vs_currencies=brl,usd"
        "&include_24hr_change=true"
    )
    cache_key = f"consultas:crypto:prices:{ids_param}"
    try:
        data = _cached_fetch_json(cache_key, url, ttl_seconds=600)
        return JsonResponse(data, json_dumps_params={'ensure_ascii': False})
    except (HTTPError, URLError, TimeoutError, ValueError) as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=502, json_dumps_params={'ensure_ascii': False})


@require_GET
def api_consultas_crypto_chart(request: HttpRequest):
    allowed_ids = {
        'bitcoin',
        'ethereum',
        'solana',
        'ripple',
        'cardano',
        'dogecoin',
    }

    coin_id = (request.GET.get('id') or '').strip().lower()
    if coin_id not in allowed_ids:
        return JsonResponse({'ok': False, 'error': 'id inválido'}, status=400, json_dumps_params={'ensure_ascii': False})

    days_raw = (request.GET.get('days') or '').strip()
    try:
        days = int(days_raw) if days_raw else 30
    except Exception:
        days = 30
    days = max(7, min(60, days))

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=brl&days={days}&interval=daily"
    cache_key = f"consultas:crypto:chart:{coin_id}:{days}"

    try:
        data = _cached_fetch_json(cache_key, url, ttl_seconds=600)
        prices = data.get('prices') if isinstance(data, dict) else None
        series = []
        if isinstance(prices, list):
            for row in prices:
                if isinstance(row, list) and len(row) >= 2 and isinstance(row[0], (int, float)) and isinstance(row[1], (int, float)):
                    dt = datetime.utcfromtimestamp(row[0] / 1000.0).date().isoformat()
                    series.append({'date': dt, 'price': float(row[1])})

        # mantém crescente por data
        series.sort(key=lambda x: x['date'])
        current = series[-1] if series else None

        return JsonResponse(
            {
                'ok': True,
                'id': coin_id,
                'days': days,
                'series': series,
                'current': current,
            },
            json_dumps_params={'ensure_ascii': False},
        )
    except (HTTPError, URLError, TimeoutError, ValueError) as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=502, json_dumps_params={'ensure_ascii': False})


@require_GET
def api_consultas_holidays_today(request: HttpRequest):
    # BR (Nager.Date). Cache mais longo: feriados não mudam durante o dia.
    today = timezone.localdate()
    year = today.year

    holidays_cache_key = f"consultas:holidays:BR:{year}"
    next_cache_key = "consultas:holidays:BR:next"

    try:
        holidays = cache.get(holidays_cache_key)
        if holidays is None:
            holidays = _http_get_json(f"https://date.nager.at/api/v3/PublicHolidays/{year}/BR")
            cache.set(holidays_cache_key, holidays, 6 * 60 * 60)

        today_str = today.isoformat()
        today_matches = [h for h in holidays if (h.get('date') == today_str)]

        next_holidays = cache.get(next_cache_key)
        if next_holidays is None:
            next_holidays = _http_get_json("https://date.nager.at/api/v3/NextPublicHolidays/BR")
            cache.set(next_cache_key, next_holidays, 6 * 60 * 60)

        next_one = next_holidays[0] if isinstance(next_holidays, list) and next_holidays else None

        return JsonResponse(
            {
                'ok': True,
                'today': today_matches,
                'next': next_one,
            },
            json_dumps_params={'ensure_ascii': False},
        )
    except (HTTPError, URLError, TimeoutError, ValueError) as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=502, json_dumps_params={'ensure_ascii': False})


def _stable_pick(seed: str, options: list[str]) -> str:
    if not options:
        return ''
    h = hashlib.md5(seed.encode('utf-8')).hexdigest()
    idx = int(h[:8], 16) % len(options)
    return options[idx]


def _day_facts_dataset() -> dict[str, list[dict]]:
    # Chave: MM-DD (datas fixas). Mantemos só coisas úteis/realmente populares.
    return {
        '01-01': [
            {'kind': 'comemorativa', 'title': 'Ano Novo', 'year': None, 'about': 'Primeiro dia do ano; muita gente usa como marco pra planos e recomeços.'},
        ],
        '03-08': [
            {'kind': 'comemorativa', 'title': 'Dia Internacional da Mulher', 'year': None, 'about': 'Data de reconhecimento e reflexão sobre direitos e igualdade.'},
        ],
        '04-21': [
            {'kind': 'feriado', 'title': 'Tiradentes (Brasil)', 'year': None, 'about': 'Feriado nacional brasileiro em homenagem a Tiradentes.'},
        ],
        '05-01': [
            {'kind': 'comemorativa', 'title': 'Dia do Trabalhador', 'year': None, 'about': 'Data ligada à história do trabalho e direitos trabalhistas.'},
        ],
        '05-08': [
            {'kind': 'fato', 'title': 'Fim da Segunda Guerra Mundial na Europa (VE Day)', 'year': 1945, 'about': 'Marca a rendição da Alemanha na Europa e o encerramento do conflito no continente.'},
        ],
        '06-05': [
            {'kind': 'comemorativa', 'title': 'Dia Mundial do Meio Ambiente', 'year': None, 'about': 'Data global para lembrar ações de preservação ambiental.'},
        ],
        '07-20': [
            {'kind': 'comemorativa', 'title': 'Dia do Amigo (Brasil)', 'year': None, 'about': 'Data popular no Brasil para celebrar amizade e vínculos.'},
        ],
        '07-30': [
            {'kind': 'comemorativa', 'title': 'Dia Internacional da Amizade (ONU)', 'year': None, 'about': 'Data internacional para incentivar amizade e cooperação.'},
        ],
        '08-11': [
            {'kind': 'comemorativa', 'title': 'Dia dos Pais (referência)', 'year': None, 'about': 'No Brasil é celebrado em agosto (data variável por ano).'},
        ],
        '09-02': [
            {'kind': 'fato', 'title': 'Fim da Segunda Guerra Mundial (assinatura da rendição do Japão)', 'year': 1945, 'about': 'Assinatura formal da rendição do Japão, marcando o fim do conflito em escala global.'},
        ],
        '09-07': [
            {'kind': 'feriado', 'title': 'Independência do Brasil', 'year': 1822, 'about': 'Feriado nacional que marca a independência do Brasil.'},
        ],
        '10-12': [
            {'kind': 'feriado', 'title': 'Nossa Senhora Aparecida (Brasil)', 'year': None, 'about': 'Feriado nacional e data religiosa importante no país.'},
            {'kind': 'comemorativa', 'title': 'Dia das Crianças (Brasil)', 'year': None, 'about': 'Data popular de celebração e consumo (presentes) no Brasil.'},
        ],
        '11-02': [
            {'kind': 'feriado', 'title': 'Finados (Brasil)', 'year': None, 'about': 'Dia de memória e homenagem aos falecidos.'},
        ],
        '11-15': [
            {'kind': 'feriado', 'title': 'Proclamação da República (Brasil)', 'year': 1889, 'about': 'Feriado nacional que marca a proclamação da República.'},
        ],
        '11-20': [
            {'kind': 'feriado', 'title': 'Dia da Consciência Negra (Brasil)', 'year': None, 'about': 'Data de reflexão sobre a luta e contribuições da população negra.'},
        ],
        '12-25': [
            {'kind': 'feriado', 'title': 'Natal', 'year': None, 'about': 'Data tradicional, com forte presença cultural e religiosa.'},
        ],
    }


def _fetch_dayfacts_from_wikipedia(date_obj):
    """Busca itens do dia via Wikipedia (pt) usando a API 'onthisday'.

    Fonte: pt.wikipedia.org (conteúdo CC BY-SA; consumimos via API pública).
    Retorna lista de dicts compatível com o endpoint, ou [].
    """
    cache_key = f"consultas:dayfacts:wikipedia:onthisday:{date_obj.isoformat()}"
    try:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        month = int(date_obj.month)
        day = int(date_obj.day)

        holidays_url = f"https://pt.wikipedia.org/api/rest_v1/feed/onthisday/holidays/{month}/{day}"
        events_url = f"https://pt.wikipedia.org/api/rest_v1/feed/onthisday/events/{month}/{day}"

        holidays_data = _http_get_json(holidays_url)
        events_data = _http_get_json(events_url)

        holidays = holidays_data.get('holidays') if isinstance(holidays_data, dict) else None
        events = events_data.get('events') if isinstance(events_data, dict) else None

        out: list[dict] = []

        def _add_items(kind: str, rows, limit: int):
            if not isinstance(rows, list):
                return
            for row in rows:
                if len(out) >= 12:
                    return
                if not isinstance(row, dict):
                    continue
                text = (row.get('text') or '').strip()
                if not text:
                    continue
                year = row.get('year')
                year_txt = f" ({year})" if isinstance(year, int) else ''

                vibe = _stable_pick(
                    f"wiki:{date_obj.isoformat()}:{kind}:{text}",
                    [
                        'Hoje tem dessas datas que ajudam a puxar contexto.',
                        'Isso costuma passar batido, mas é bem interessante.',
                        'Se você curte curiosidade prática: anota essa.',
                        'Pra lembrar e comentar no dia: fica ótimo.',
                    ],
                )
                why = _stable_pick(
                    f"wiki:{date_obj.isoformat()}:{kind}:{text}:why",
                    [
                        'Serve como referência cultural e aparece em calendários e notícias.',
                        'Ajuda a entender por que algumas datas viram “marco” na conversa pública.',
                        'É um ótimo gancho pra organizar agenda e conteúdo do dia.',
                    ],
                )

                out.append(
                    {
                        'kind': kind,
                        'title': f"{text}{year_txt}",
                        'about': '',
                        'ia_summary': f"{vibe} {why}",
                        'source': 'wikipedia',
                    }
                )

        _add_items('comemorativa', holidays, limit=8)
        _add_items('fato', events, limit=6)

        cache.set(cache_key, out, 6 * 60 * 60)
        return out
    except Exception:
        return []


@require_GET
def api_consultas_dayfacts_today(request: HttpRequest):
    today = timezone.localdate()
    # 1) tenta fontes (Wikipedia)
    out = _fetch_dayfacts_from_wikipedia(today)

    # 2) fallback: dataset interno
    if not out:
        key = today.strftime('%m-%d')
        items = _day_facts_dataset().get(key, [])

        for idx, item in enumerate(items):
            title = item.get('title') or 'Curiosidade'
            about = item.get('about') or ''
            year = item.get('year')
            kind = item.get('kind') or 'comemorativa'

            vibe = _stable_pick(
                f"{today.isoformat()}:{title}:{idx}",
                [
                    'Hoje é um daqueles dias que vale marcar no calendário.',
                    'Dá pra usar isso como gancho pra uma conversa boa.',
                    'Se você gosta de contexto, essa data é um prato cheio.',
                    'Curiosidade útil pra não passar batido no dia.',
                ],
            )
            why = _stable_pick(
                f"{today.isoformat()}:{title}:why:{idx}",
                [
                    'Por que isso importa: muda a agenda, o humor do país ou a rotina de muita gente.',
                    'Por que isso importa: vira referência cultural e aparece muito em notícias e calendários.',
                    'Por que isso importa: é um marco que ajuda a entender o presente.',
                ],
            )

            year_txt = f" ({year})" if isinstance(year, int) else ''
            ia_summary = f"{vibe} {about} {why}".strip()

            out.append(
                {
                    'kind': kind,
                    'title': f"{title}{year_txt}",
                    'about': about,
                    'ia_summary': ia_summary,
                    'source': 'dataset',
                }
            )

    return JsonResponse(
        {
            'ok': True,
            'date': today.isoformat(),
            'items': out,
        },
        json_dumps_params={'ensure_ascii': False},
    )
