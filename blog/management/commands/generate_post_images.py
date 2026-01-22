from __future__ import annotations

import io
import random
from dataclasses import dataclass
import re

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from blog.models import Post


@dataclass(frozen=True)
class Theme:
    name: str
    bg1: tuple[int, int, int]
    bg2: tuple[int, int, int]
    accent: tuple[int, int, int]
    icon: str


THEMES: dict[str, Theme] = {
    'esportes': Theme(
        name='Esportes',
        bg1=(6, 95, 70),
        bg2=(16, 185, 129),
        accent=(245, 158, 11),
        icon='⚽',
    ),
    'politica': Theme(
        name='Política',
        bg1=(17, 24, 39),
        bg2=(239, 68, 68),
        accent=(255, 255, 255),
        icon='🏛️',
    ),
    'empreendedorismo': Theme(
        name='Empreendedorismo',
        bg1=(30, 41, 59),
        bg2=(59, 130, 246),
        accent=(16, 185, 129),
        icon='🚀',
    ),
    'alphaville': Theme(
        name='Alphaville',
        bg1=(2, 6, 23),
        bg2=(168, 85, 247),
        accent=(236, 254, 255),
        icon='🏙️',
    ),
    'geral': Theme(
        name='Oxira',
        bg1=(15, 23, 42),
        bg2=(71, 85, 105),
        accent=(248, 113, 113),
        icon='📰',
    ),
}


def _pick_theme(post: Post) -> Theme:
    slug = ''
    if post.category_id and post.category and post.category.slug:
        slug = post.category.slug.lower()

    for key in ('esportes', 'politica', 'empreendedorismo', 'alphaville'):
        if key in slug:
            return THEMES[key]

    return THEMES['geral']


def _wrap_text(text: str, max_chars: int) -> list[str]:
    words = (text or '').strip().split()
    if not words:
        return ['']

    lines: list[str] = []
    current: list[str] = []
    cur_len = 0
    for w in words:
        extra = (1 if current else 0) + len(w)
        if cur_len + extra <= max_chars:
            current.append(w)
            cur_len += extra
        else:
            lines.append(' '.join(current))
            current = [w]
            cur_len = len(w)
    if current:
        lines.append(' '.join(current))

    return lines[:5]


def _load_font(size: int):
    # Tenta fontes comuns do Windows; se falhar, usa default.
    from PIL import ImageFont

    candidates = [
        r"C:\\Windows\\Fonts\\arialbd.ttf",
        r"C:\\Windows\\Fonts\\arial.ttf",
        r"C:\\Windows\\Fonts\\segoeuib.ttf",
        r"C:\\Windows\\Fonts\\segoeui.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _topic_key(title: str, category_slug: str) -> str:
    t = (title or '').lower()

    if re.search(r'olimp', t):
        return 'olympics'
    if re.search(r'\bia\b|intelig[êe]ncia artificial|tecnologia|varejo', t):
        return 'ai'
    if re.search(r'campeon|t[áa]tica|jogo|futebol|partida', t):
        return 'soccer'
    if re.search(r'startup|startups|lucro|ebitda|neg[oó]cio', t):
        return 'startup'
    if re.search(r'lei|congresso|zoneamento|pol[ií]tica', t):
        return 'politics'
    if re.search(r'gastron|restaurante|chef|luxo', t):
        return 'food'
    if re.search(r'alphaville', t):
        return 'city'

    s = (category_slug or '').lower()
    if 'esportes' in s:
        return 'sports'
    if 'politica' in s:
        return 'politics'
    if 'empreendedorismo' in s:
        return 'startup'
    if 'alphaville' in s:
        return 'city'
    return 'news'


def _draw_topic_illustration(img, theme: Theme, topic: str):
    from PIL import Image, ImageDraw

    width, height = img.size
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # região principal (parte de cima)
    top_h = int(height * 0.62)
    cx = int(width * 0.55)
    cy = int(top_h * 0.55)

    def stroke_circle(x, y, r, color, w=14):
        d.ellipse([x - r, y - r, x + r, y + r], outline=color, width=w)

    if topic == 'olympics':
        r = int(min(width, height) * 0.08)
        gap = int(r * 0.25)
        x0 = int(width * 0.30)
        y0 = int(top_h * 0.35)
        colors = [
            (59, 130, 246, 210),   # blue
            (245, 158, 11, 210),   # yellow
            (0, 0, 0, 210),        # black
            (16, 185, 129, 210),   # green
            (239, 68, 68, 210),    # red
        ]
        # 1ª linha: azul, preto, vermelho
        stroke_circle(x0 + 0 * (2 * r + gap), y0, r, colors[0])
        stroke_circle(x0 + 1 * (2 * r + gap), y0, r, colors[2])
        stroke_circle(x0 + 2 * (2 * r + gap), y0, r, colors[4])
        # 2ª linha: amarelo, verde
        stroke_circle(x0 + int(0.5 * (2 * r + gap)), y0 + r + int(gap * 0.7), r, colors[1])
        stroke_circle(x0 + int(1.5 * (2 * r + gap)), y0 + r + int(gap * 0.7), r, colors[3])

    elif topic in ('soccer', 'sports'):
        r = int(min(width, height) * 0.16)
        # bola
        stroke_circle(cx, cy, r, (255, 255, 255, 190), w=18)
        d.ellipse([cx - r + 18, cy - r + 18, cx + r - 18, cy + r - 18], outline=(0, 0, 0, 85), width=6)
        # pentágono central simples
        poly = [
            (cx, cy - int(r * 0.35)),
            (cx + int(r * 0.33), cy - int(r * 0.10)),
            (cx + int(r * 0.20), cy + int(r * 0.28)),
            (cx - int(r * 0.20), cy + int(r * 0.28)),
            (cx - int(r * 0.33), cy - int(r * 0.10)),
        ]
        d.polygon(poly, fill=(0, 0, 0, 110))
        # linhas
        for ang in (-40, 40, 140):
            dx = int(r * 0.9)
            dy = int(r * 0.25)
            d.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], fill=(255, 255, 255, 55), width=6)

    elif topic in ('startup', 'news'):
        # foguete estilizado
        body_w = int(width * 0.14)
        body_h = int(top_h * 0.32)
        x = int(width * 0.58)
        y = int(top_h * 0.22)
        d.rounded_rectangle([x, y, x + body_w, y + body_h], radius=body_w // 2, fill=(255, 255, 255, 130))
        # nariz
        d.polygon([(x, y), (x + body_w, y), (x + body_w // 2, y - int(body_w * 0.8))], fill=(255, 255, 255, 155))
        # janela
        w_r = int(body_w * 0.18)
        d.ellipse([
            x + body_w // 2 - w_r,
            y + int(body_h * 0.35) - w_r,
            x + body_w // 2 + w_r,
            y + int(body_h * 0.35) + w_r,
        ], fill=(theme.accent[0], theme.accent[1], theme.accent[2], 180))
        # chama
        flame_y = y + body_h
        d.polygon(
            [
                (x + body_w // 2, flame_y + int(body_w * 0.9)),
                (x + int(body_w * 0.25), flame_y + int(body_w * 0.15)),
                (x + int(body_w * 0.75), flame_y + int(body_w * 0.15)),
            ],
            fill=(245, 158, 11, 190),
        )

    elif topic == 'ai':
        # circuito + sacola
        node_col = (236, 254, 255, 180)
        line_col = (236, 254, 255, 90)
        nodes = [
            (int(width * 0.40), int(top_h * 0.25)),
            (int(width * 0.58), int(top_h * 0.22)),
            (int(width * 0.68), int(top_h * 0.36)),
            (int(width * 0.52), int(top_h * 0.42)),
            (int(width * 0.38), int(top_h * 0.45)),
            (int(width * 0.62), int(top_h * 0.52)),
        ]
        for i in range(len(nodes) - 1):
            d.line([nodes[i], nodes[i + 1]], fill=line_col, width=10)
        for (nx, ny) in nodes:
            d.ellipse([nx - 18, ny - 18, nx + 18, ny + 18], fill=node_col)

        bx = int(width * 0.70)
        by = int(top_h * 0.22)
        bw = int(width * 0.12)
        bh = int(top_h * 0.22)
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=18, fill=(255, 255, 255, 120))
        # alça
        d.arc([bx + 10, by - 28, bx + bw - 10, by + 36], start=200, end=-20, fill=(255, 255, 255, 160), width=8)

    elif topic == 'politics':
        # prédio com colunas + "martelo" simples
        px = int(width * 0.46)
        py = int(top_h * 0.22)
        pw = int(width * 0.28)
        ph = int(top_h * 0.32)
        d.rectangle([px, py, px + pw, py + ph], fill=(255, 255, 255, 120))
        d.polygon([(px, py), (px + pw, py), (px + pw // 2, py - int(ph * 0.35))], fill=(255, 255, 255, 145))
        col_w = pw // 7
        for i in range(1, 6):
            x = px + i * col_w
            d.rectangle([x, py + int(ph * 0.18), x + int(col_w * 0.45), py + ph], fill=(0, 0, 0, 40))
        # gavel
        gx = int(width * 0.34)
        gy = int(top_h * 0.50)
        d.rectangle([gx, gy, gx + 110, gy + 46], fill=(0, 0, 0, 55))
        d.rectangle([gx + 78, gy - 70, gx + 110, gy + 120], fill=(0, 0, 0, 55))

    elif topic == 'food':
        # garfo e faca
        fx = int(width * 0.46)
        fy = int(top_h * 0.18)
        fh = int(top_h * 0.44)
        # faca
        d.rounded_rectangle([fx, fy, fx + 40, fy + fh], radius=18, fill=(255, 255, 255, 130))
        # garfo
        gx = fx + 90
        d.rounded_rectangle([gx, fy + 40, gx + 40, fy + fh], radius=18, fill=(255, 255, 255, 130))
        for i in range(4):
            d.rectangle([gx + i * 10, fy, gx + i * 10 + 6, fy + 70], fill=(255, 255, 255, 150))

    elif topic == 'city':
        # skyline
        base_y = int(top_h * 0.60)
        x = int(width * 0.30)
        for w, h in [(120, 240), (180, 320), (140, 280), (220, 360), (150, 260)]:
            d.rectangle([x, base_y - h, x + w, base_y], fill=(255, 255, 255, 110))
            # janelas
            for wx in range(x + 18, x + w - 18, 28):
                for wy in range(base_y - h + 22, base_y - 18, 34):
                    d.rectangle([wx, wy, wx + 10, wy + 16], fill=(0, 0, 0, 35))
            x += w + 24

    # vinheta leve
    vignette = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    vd.rectangle([0, 0, width, int(height * 0.70)], fill=(0, 0, 0, 35))

    img = Image.alpha_composite(img.convert('RGBA'), overlay)
    img = Image.alpha_composite(img, vignette)
    return img.convert('RGB')


def _make_image_bytes(post: Post, theme: Theme, size: tuple[int, int]) -> bytes:
    from PIL import Image, ImageDraw

    width, height = size

    # Fundo em gradiente simples (vertical)
    img = Image.new('RGB', (width, height), theme.bg1)
    draw = ImageDraw.Draw(img)

    for y in range(height):
        t = y / max(1, height - 1)
        r = int(theme.bg1[0] * (1 - t) + theme.bg2[0] * t)
        g = int(theme.bg1[1] * (1 - t) + theme.bg2[1] * t)
        b = int(theme.bg1[2] * (1 - t) + theme.bg2[2] * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Ilustração relacionada ao tema/título (bem mais contextual que ruído aleatório)
    cat_slug = ''
    try:
        if post.category and post.category.slug:
            cat_slug = post.category.slug
    except Exception:
        cat_slug = ''
    topic = _topic_key(post.title, cat_slug)
    img = _draw_topic_illustration(img, theme, topic)
    draw = ImageDraw.Draw(img)

    # Barra inferior (tipo tarja)
    bar_h = int(height * 0.33)
    draw.rectangle([0, height - bar_h, width, height], fill=(0, 0, 0))

    # Texto
    title = (post.title or '').strip()
    cat = theme.name

    font_title = _load_font(int(height * 0.09))
    font_meta = _load_font(int(height * 0.05))

    # Categoria (sem depender de emoji para "parecer tema")
    meta_text = f"{cat.upper()}"
    draw.text((40, height - bar_h + 28), meta_text, fill=(255, 255, 255), font=font_meta)

    # Título quebrado
    lines = _wrap_text(title, max_chars=32)

    x = 40
    y = height - bar_h + 28 + int(height * 0.07)
    line_gap = int(height * 0.012)

    for line in lines:
        draw.text((x, y), line, fill=(255, 255, 255), font=font_title)
        y += font_title.size + line_gap

    # Marca pequena
    draw.text((40, 26), "OXIRA", fill=(255, 255, 255), font=font_meta)

    out = io.BytesIO()
    img.save(out, format='JPEG', quality=90, optimize=True)
    return out.getvalue()


class Command(BaseCommand):
    help = (
        "Gera imagens de destaque (placeholders) para posts que ainda estão sem imagem. "
        "As imagens são geradas localmente, com visual por tema/categoria."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Gera/substitui imagens mesmo para posts que já têm imagem.',
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
            default=1280,
            help='Largura da imagem (padrão 1280).',
        )
        parser.add_argument(
            '--height',
            type=int,
            default=720,
            help='Altura da imagem (padrão 720).',
        )

    def handle(self, *args, **options):
        replace_all: bool = bool(options['all'])
        limit: int = int(options['limit'] or 0)
        width: int = int(options['width'] or 1280)
        height: int = int(options['height'] or 720)

        qs = Post.objects.select_related('category').order_by('-published_date')
        if not replace_all:
            qs = qs.filter(image__isnull=True) | qs.filter(image='')
            qs = qs.select_related('category').order_by('-published_date')

        posts = list(qs[:limit] if limit > 0 else qs)
        if not posts:
            self.stdout.write(self.style.SUCCESS('Nenhum post para processar.'))
            return

        processed = 0
        for post in posts:
            if not replace_all and post.image:
                continue

            theme = _pick_theme(post)
            img_bytes = _make_image_bytes(post, theme, (width, height))

            filename = f"{post.slug}.jpg"
            # upload_to='posts/'
            post.image.save(filename, ContentFile(img_bytes), save=True)

            processed += 1
            self.stdout.write(f"OK: {post.slug} -> posts/{filename} ({theme.name})")

        self.stdout.write(self.style.SUCCESS(f"Concluído: {processed} imagem(ns) gerada(s)."))
