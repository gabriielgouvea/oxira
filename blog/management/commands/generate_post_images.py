from __future__ import annotations

import io
import random
from dataclasses import dataclass

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

    # Shapes/ruído leve pra não ficar “chapado”
    random.seed(post.slug)
    for _ in range(18):
        x1 = random.randint(-50, width - 50)
        y1 = random.randint(-50, height - 50)
        x2 = x1 + random.randint(80, 220)
        y2 = y1 + random.randint(80, 220)
        alpha = random.randint(18, 40)
        col = (
            min(255, theme.accent[0] + random.randint(-20, 20)),
            min(255, theme.accent[1] + random.randint(-20, 20)),
            min(255, theme.accent[2] + random.randint(-20, 20)),
            alpha,
        )
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.ellipse([x1, y1, x2, y2], fill=col)
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(img)

    # Barra inferior (tipo tarja)
    bar_h = int(height * 0.33)
    draw.rectangle([0, height - bar_h, width, height], fill=(0, 0, 0))

    # Texto
    title = (post.title or '').strip()
    cat = theme.name

    font_title = _load_font(int(height * 0.09))
    font_meta = _load_font(int(height * 0.05))

    # Ícone + categoria
    meta_text = f"{theme.icon}  {cat.upper()}"
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
