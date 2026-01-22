from __future__ import annotations

from django.core.management.base import BaseCommand

from blog.models import Post


class Command(BaseCommand):
    help = "Remove todas as imagens destacadas (Post.image) dos posts e apaga os arquivos do storage."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Não altera nada; só mostra o que seria removido.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Limita a quantidade de posts processados (0 = sem limite).',
        )

    def handle(self, *args, **options):
        dry_run: bool = bool(options['dry_run'])
        limit: int = int(options['limit'] or 0)

        qs = Post.objects.exclude(image__isnull=True).exclude(image='').order_by('-published_date')
        posts = list(qs[:limit] if limit > 0 else qs)

        if not posts:
            self.stdout.write(self.style.SUCCESS('Nenhum post com imagem para limpar.'))
            return

        removed = 0
        for post in posts:
            name = getattr(post.image, 'name', '') if post.image else ''
            self.stdout.write(f"REMOVER: {post.slug} -> {name}")

            if dry_run:
                continue

            try:
                # apaga arquivo do storage
                post.image.delete(save=False)
            except Exception:
                pass

            post.image = None
            post.save(update_fields=['image'])
            removed += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry-run: {len(posts)} imagem(ns) seriam removidas."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Concluído: {removed} imagem(ns) removidas."))
