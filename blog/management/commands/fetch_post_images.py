from __future__ import annotations

import io
import re
import time
import urllib.parse
from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Q

from blog.models import Post


@dataclass(frozen=True)
class CommonsImage:
    page_title: str
    thumb_url: str
    description_url: str | None
    license_short: str | None
    artist: str | None
    attribution_required: bool


STOPWORDS_PT = {
    'a', 'o', 'os', 'as', 'um', 'uma', 'uns', 'umas',
    'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
    'e', 'ou', 'com', 'para', 'por', 'sobre', 'sem',
    'como', 'que', 'se', 'é', 'ao', 'à', 'às', 'aos',
    'das', 'dos', 'uma', 'mais', 'menos', 'nova', 'novo',
}


TITLE_TO_QUERY_HINTS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r'olimp', re.I), ['Olympics', 'Olympic games', 'athletics']),
    (re.compile(r'campeonat|t[áa]tica|jogo|futebol', re.I), ['football match', 'soccer', 'stadium']),
    (re.compile(r'startup|startups', re.I), ['startup', 'entrepreneurship', 'business']),
    (re.compile(r'\bia\b|intelig[êe]ncia artificial', re.I), ['artificial intelligence', 'technology', 'retail']),
    (re.compile(r'varejo', re.I), ['retail', 'store', 'shopping']),
    (re.compile(r'congresso|lei|zoneamento', re.I), ['parliament', 'congress', 'city planning']),
    (re.compile(r'gastron', re.I), ['restaurant', 'fine dining', 'chef']),
    (re.compile(r'alphaville', re.I), ['city skyline', 'urban', 'cityscape']),
]

CATEGORY_HINTS: list[tuple[str, list[str]]] = [
    ('esportes', ['sports', 'athletics']),
    ('politica', ['politics', 'government']),
    ('empreendedorismo', ['business', 'entrepreneurship']),
    ('alphaville', ['city', 'urban']),
]


def _http_get_json(url: str, timeout: float = 10.0) -> dict:
    from urllib.request import Request, urlopen

    req = Request(
        url,
        headers={
            'User-Agent': 'Oxira/1.0 (dev; fetch_post_images)',
            'Accept': 'application/json',
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
    import json

    return json.loads(raw)


def _download_bytes(url: str, timeout: float = 20.0) -> bytes:
    from urllib.request import Request, urlopen

    req = Request(
        url,
        headers={
            'User-Agent': 'Oxira/1.0 (dev; fetch_post_images)',
            'Accept': 'image/*,*/*;q=0.8',
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _sleep(seconds: float):
    try:
        time.sleep(max(0.0, float(seconds)))
    except Exception:
        pass


def _with_retries(fn, *, tries: int, base_sleep: float, what: str):
    from urllib.error import HTTPError

    last_exc: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except HTTPError as e:
            last_exc = e
            status = getattr(e, 'code', None)
            if status == 429 and attempt < tries:
                retry_after = None
                try:
                    retry_after = e.headers.get('Retry-After')
                except Exception:
                    retry_after = None

                wait = float(retry_after) if retry_after and str(retry_after).isdigit() else (base_sleep * (2 ** (attempt - 1)))
                _sleep(wait)
                continue
            raise
        except Exception as e:
            last_exc = e
            if attempt < tries:
                _sleep(base_sleep * (2 ** (attempt - 1)))
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Falha inesperada em {what}")


def _slug_category(post: Post) -> str:
    try:
        if post.category and post.category.slug:
            return post.category.slug.lower()
    except Exception:
        pass
    return ''


def _basic_keywords(title: str) -> list[str]:
    # Extrai palavras razoáveis do título (pt-BR) para usar como query.
    words = re.findall(r"[\wÀ-ÿ'-]+", (title or '').lower())
    cleaned = []
    for w in words:
        w = w.strip("'-")
        if len(w) < 4:
            continue
        if w in STOPWORDS_PT:
            continue
        cleaned.append(w)
    # Remove duplicados preservando ordem
    out: list[str] = []
    for w in cleaned:
        if w not in out:
            out.append(w)
    return out[:8]


def _build_queries(post: Post) -> list[str]:
    title = (post.title or '').strip()
    cat_slug = _slug_category(post)

    hints: list[str] = []
    for pattern, candidates in TITLE_TO_QUERY_HINTS:
        if pattern.search(title):
            hints.extend(candidates)
            break

    for key, candidates in CATEGORY_HINTS:
        if key in cat_slug:
            hints.extend(candidates)
            break

    keywords = _basic_keywords(title)

    queries: list[str] = []

    # 1) Dica (EN) + keywords
    if hints and keywords:
        queries.append(' '.join([hints[0], *keywords[:4]]))

    # 2) Só dica
    if hints:
        queries.append(hints[0])

    # 3) Só título (pode funcionar)
    if title:
        queries.append(title)

    # 4) Keywords
    if keywords:
        queries.append(' '.join(keywords[:6]))

    # Dedup
    out: list[str] = []
    for q in queries:
        q = q.strip()
        if q and q not in out:
            out.append(q)
    return out[:5]


def _parse_extmetadata(meta: dict) -> tuple[str | None, str | None, bool]:
    # extmetadata fields are dicts: {"value": "..."}
    def val(k: str) -> str | None:
        v = meta.get(k)
        if isinstance(v, dict):
            s = v.get('value')
            if isinstance(s, str):
                return s
        return None

    license_short = val('LicenseShortName') or val('UsageTerms')
    artist = val('Artist')
    attribution = val('Attribution')
    attribution_required = bool(attribution)  # heurística simples
    return license_short, artist, attribution_required


def _search_commons_images(query: str, width: int) -> list[CommonsImage]:
    # Busca no namespace 6 (File:) do Wikimedia Commons.
    params = {
        'action': 'query',
        'format': 'json',
        'generator': 'search',
        'gsrnamespace': '6',
        'gsrsearch': query,
        'gsrlimit': '8',
        'prop': 'imageinfo',
        'iiprop': 'url|extmetadata',
        'iiurlwidth': str(width),
        'redirects': '1',
    }
    url = 'https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode(params)
    data = _with_retries(lambda: _http_get_json(url), tries=3, base_sleep=2.0, what='commons search')

    pages = (data.get('query') or {}).get('pages')
    if not isinstance(pages, dict):
        return []

    out: list[CommonsImage] = []
    for _, page in pages.items():
        if not isinstance(page, dict):
            continue
        title = page.get('title')
        imageinfo = page.get('imageinfo')
        if not isinstance(title, str) or not isinstance(imageinfo, list) or not imageinfo:
            continue
        ii0 = imageinfo[0]
        if not isinstance(ii0, dict):
            continue
        thumb_url = ii0.get('thumburl') or ii0.get('url')
        desc_url = ii0.get('descriptionurl')
        meta = ii0.get('extmetadata')
        if not isinstance(thumb_url, str):
            continue

        license_short = None
        artist = None
        attribution_required = False
        if isinstance(meta, dict):
            license_short, artist, attribution_required = _parse_extmetadata(meta)

        out.append(
            CommonsImage(
                page_title=title,
                thumb_url=thumb_url,
                description_url=desc_url if isinstance(desc_url, str) else None,
                license_short=license_short,
                artist=artist,
                attribution_required=attribution_required,
            )
        )

    return out


def _to_jpeg_bytes(image_bytes: bytes, max_w: int) -> bytes:
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert('RGB')
        w, h = img.size
        if w > max_w:
            new_h = int(h * (max_w / w))
            img = img.resize((max_w, new_h), Image.LANCZOS)

        out = io.BytesIO()
        img.save(out, format='JPEG', quality=90, optimize=True)
        return out.getvalue()


def _download_unsplash_bytes(query: str, *, width: int, height: int) -> tuple[bytes, str]:
    # Endpoint público de preview (sem chave). Observação: não retorna metadados de autoria.
    # Para produção, ideal é usar API oficial e exibir créditos conforme termos.
    q = urllib.parse.quote(query.strip())
    url = f"https://source.unsplash.com/{width}x{height}/?{q}"
    raw = _download_bytes(url)
    return raw, url


def _append_credit(post: Post, credit_line: str) -> None:
    existing = (post.internal_notes or '').strip()
    if credit_line in existing:
        return
    if existing:
        post.internal_notes = existing + "\n" + credit_line
    else:
        post.internal_notes = credit_line


class Command(BaseCommand):
    help = (
        "Baixa fotos relevantes do Wikimedia Commons (por título/categoria) e define como imagem destacada do post. "
        "Salva uma linha de crédito/licença em internal_notes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Substitui imagens existentes (use para trocar placeholders).',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Limita a quantidade de posts processados (0 = sem limite).',
        )
        parser.add_argument(
            '--width',
            type=int,
            default=1600,
            help='Largura alvo usada pela API (thumb) e conversão (padrão 1600).',
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=1.2,
            help='Pausa (segundos) entre chamadas externas (padrão 1.2).',
        )
        parser.add_argument(
            '--slugs',
            type=str,
            default='',
            help='Processa apenas esses slugs (separados por vírgula).',
        )
        parser.add_argument(
            '--provider',
            type=str,
            default='auto',
            choices=['auto', 'commons', 'unsplash'],
            help='Fonte das imagens: auto (commons e fallback), commons, unsplash.',
        )

    def handle(self, *args, **options):
        replace: bool = bool(options['replace'])
        limit: int = int(options['limit'] or 0)
        width: int = int(options['width'] or 1600)
        sleep_s: float = float(options['sleep'] or 0.0)
        slugs_raw: str = str(options['slugs'] or '').strip()
        slugs: list[str] = [s.strip() for s in slugs_raw.split(',') if s.strip()] if slugs_raw else []
        provider: str = str(options['provider'] or 'auto').strip().lower()

        qs = Post.objects.select_related('category').order_by('-published_date')
        if slugs:
            qs = qs.filter(slug__in=slugs)
        if not replace:
            qs = qs.filter(Q(image__isnull=True) | Q(image=''))

        posts = list(qs[:limit] if limit > 0 else qs)
        if not posts:
            self.stdout.write(self.style.SUCCESS('Nenhum post para processar.'))
            return

        processed = 0
        skipped = 0

        for post in posts:
            if (not replace) and post.image:
                skipped += 1
                continue

            queries = _build_queries(post)
            picked: CommonsImage | None = None
            picked_query = None

            if provider in ('auto', 'commons'):
                for q in queries:
                    _sleep(sleep_s)
                    results = _search_commons_images(q, width=width)
                    if results:
                        picked = results[0]
                        picked_query = q
                        break

            if provider == 'commons' and not picked:
                self.stdout.write(self.style.WARNING(f"SEM RESULTADO (commons): {post.slug} ({post.title})"))
                continue

            try:
                filename = f"{post.slug}.jpg"

                # 1) Wikimedia Commons (preferencial)
                if picked is not None:
                    _sleep(sleep_s)
                    raw = _with_retries(lambda: _download_bytes(picked.thumb_url), tries=3, base_sleep=2.0, what='commons download')
                    jpg = _to_jpeg_bytes(raw, max_w=width)
                    post.image.save(filename, ContentFile(jpg), save=False)

                    credit_bits = [
                        'Wikimedia Commons',
                        f"file={picked.page_title}",
                    ]
                    if picked.description_url:
                        credit_bits.append(picked.description_url)
                    if picked.license_short:
                        credit_bits.append(f"license={picked.license_short}")
                    if picked.artist:
                        artist_clean = re.sub(r"\s+", " ", picked.artist).strip()
                        credit_bits.append(f"artist={artist_clean[:120]}")

                    credit_line = "Imagem: " + " | ".join(credit_bits)
                    _append_credit(post, credit_line)

                    post.save(update_fields=['image', 'internal_notes'])
                    processed += 1
                    self.stdout.write(self.style.SUCCESS(f"OK: {post.slug} <- commons '{picked_query}'"))
                    continue

                # 2) Fallback: Unsplash Source (preview)
                if provider in ('auto', 'unsplash'):
                    q = queries[0] if queries else (post.title or 'news')
                    _sleep(sleep_s)
                    raw_u, src_url = _with_retries(
                        lambda: _download_unsplash_bytes(q, width=width, height=int(width * 9 / 16)),
                        tries=3,
                        base_sleep=2.0,
                        what='unsplash download',
                    )
                    jpg = _to_jpeg_bytes(raw_u, max_w=width)
                    post.image.save(filename, ContentFile(jpg), save=False)
                    _append_credit(post, f"Imagem: Unsplash Source (preview) | query={q} | url={src_url}")
                    post.save(update_fields=['image', 'internal_notes'])
                    processed += 1
                    self.stdout.write(self.style.SUCCESS(f"OK: {post.slug} <- unsplash '{q}'"))
                    continue

                self.stdout.write(self.style.WARNING(f"SEM RESULTADO: {post.slug} ({post.title})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"ERRO: {post.slug} ({type(e).__name__}): {e}"))

        self.stdout.write(self.style.SUCCESS(f"Concluído: {processed} ok, {skipped} pulado(s)."))
