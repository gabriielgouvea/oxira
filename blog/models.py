from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from ckeditor_uploader.fields import RichTextUploadingField
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models_ads import AdConfig

from PIL import Image, ImageOps

# Perfil do Usuário (Avatar, Bio, etc)
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Foto de Perfil")
    # Crop do avatar (coordenadas em pixels na imagem original)
    avatar_crop_x = models.PositiveIntegerField(blank=True, null=True)
    avatar_crop_y = models.PositiveIntegerField(blank=True, null=True)
    avatar_crop_w = models.PositiveIntegerField(blank=True, null=True)
    avatar_crop_h = models.PositiveIntegerField(blank=True, null=True)
    bio = models.TextField(blank=True, verbose_name="Biografia")

    # Redes sociais / presença online (opcional)
    website = models.URLField(blank=True, null=True, verbose_name="Site")
    instagram = models.URLField(blank=True, null=True, verbose_name="Instagram")
    twitter = models.URLField(blank=True, null=True, verbose_name="X/Twitter")
    linkedin = models.URLField(blank=True, null=True, verbose_name="LinkedIn")
    facebook = models.URLField(blank=True, null=True, verbose_name="Facebook")

    # Dados de Contato e Endereço
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone")
    cpf = models.CharField(max_length=14, blank=True, null=True, verbose_name="CPF")
    
    cep = models.CharField(max_length=9, blank=True, null=True, verbose_name="CEP")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Endereço")
    number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número")
    complement = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    neighborhood = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bairro")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cidade")
    state = models.CharField(max_length=2, blank=True, null=True, verbose_name="Estado")

    role = models.CharField(
        max_length=20,
        choices=[
            ('admin', 'Administrador'),
            ('author', 'Autor'),
        ],
        default='author',
        verbose_name="Função no Blog",
    )
    
    # Permissões Específicas
    allowed_categories = models.ManyToManyField('Category', blank=True, verbose_name="Pode publicar em (Categorias)")

    def __str__(self):
        return f"Perfil de {self.user.username}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._apply_avatar_crop_if_needed()

    def _apply_avatar_crop_if_needed(self):
        if not self.avatar:
            return
        if not (self.avatar_crop_w and self.avatar_crop_h):
            return

        # Abre/corta/redimensiona para um quadrado padrão
        try:
            path = self.avatar.path
        except Exception:
            return

        try:
            with Image.open(path) as im:
                im = ImageOps.exif_transpose(im)
                x = int(self.avatar_crop_x or 0)
                y = int(self.avatar_crop_y or 0)
                w = int(self.avatar_crop_w or 0)
                h = int(self.avatar_crop_h or 0)
                if w <= 0 or h <= 0:
                    return
                # Clamp
                x = max(0, min(x, im.width - 1))
                y = max(0, min(y, im.height - 1))
                x2 = max(x + 1, min(x + w, im.width))
                y2 = max(y + 1, min(y + h, im.height))

                cropped = im.crop((x, y, x2, y2)).convert('RGB')
                cropped = cropped.resize((400, 400), Image.Resampling.LANCZOS)

                # Salva sobrescrevendo o arquivo original
                cropped.save(path, format='JPEG', quality=88, optimize=True, progressive=True)
        except Exception:
            return

        # Limpa o crop para não aplicar novamente em futuros saves
        type(self).objects.filter(pk=self.pk).update(
            avatar_crop_x=None,
            avatar_crop_y=None,
            avatar_crop_w=None,
            avatar_crop_h=None,
        )

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Em bases existentes pode haver usuários sem perfil (ex.: superuser criado antes da migração).
    profile, _ = UserProfile.objects.get_or_create(user=instance)
    profile.save()

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, verbose_name="Descrição (SEO)")
    order = models.IntegerField(default=0, verbose_name="Ordem de Exibição")

    class Meta:
        verbose_name_plural = "Categorias"
        verbose_name = "Categoria"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

class Post(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Rascunho'),
        ('review', 'Em Revisão'),
        ('published', 'Publicado'),
        ('scheduled', 'Agendado'),
    )

    title = models.CharField(max_length=200, blank=True, verbose_name="Título")
    subtitle = models.CharField(max_length=255, blank=True, verbose_name="Subtítulo")
    slug = models.SlugField(unique=True, null=True, blank=True, help_text="URL amigável gerada automaticamente")
    
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts', verbose_name="Autor")
    
    # Conteúdo e Mídia
    content = RichTextUploadingField(verbose_name="Conteúdo")
    image = models.ImageField(upload_to='posts/', blank=True, null=True, verbose_name="Imagem Destacada")
    # Crop da imagem destacada (coordenadas em pixels na imagem original)
    image_crop_x = models.PositiveIntegerField(blank=True, null=True)
    image_crop_y = models.PositiveIntegerField(blank=True, null=True)
    image_crop_w = models.PositiveIntegerField(blank=True, null=True)
    image_crop_h = models.PositiveIntegerField(blank=True, null=True)
    
    # SEO
    meta_description = models.CharField(max_length=160, blank=True, verbose_name="Meta Descrição (SEO)")
    keywords = models.CharField(max_length=255, blank=True, verbose_name="Palavras-chave (Separadas por vírgula)")
    
    # Controle Editorial
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft', verbose_name="Status")
    published_date = models.DateTimeField(default=timezone.now, verbose_name="Data de Publicação")
    created_date = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_date = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='posts', verbose_name="Categoria Principal")
    internal_notes = models.TextField(blank=True, verbose_name="Observações Internas (Pauta)")

    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"
        ordering = ['-published_date']

    def __str__(self):
        return self.title or f"Post #{self.pk}" if self.pk else "(Sem título)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._apply_image_crop_if_needed()

    def _apply_image_crop_if_needed(self):
        if not self.image:
            return
        if not (self.image_crop_w and self.image_crop_h):
            return

        try:
            path = self.image.path
        except Exception:
            return

        try:
            with Image.open(path) as im:
                im = ImageOps.exif_transpose(im)
                x = int(self.image_crop_x or 0)
                y = int(self.image_crop_y or 0)
                w = int(self.image_crop_w or 0)
                h = int(self.image_crop_h or 0)
                if w <= 0 or h <= 0:
                    return
                x = max(0, min(x, im.width - 1))
                y = max(0, min(y, im.height - 1))
                x2 = max(x + 1, min(x + w, im.width))
                y2 = max(y + 1, min(y + h, im.height))

                cropped = im.crop((x, y, x2, y2)).convert('RGB')
                # Tamanho padrão de capa: 1280x720 (16:9)
                cropped = cropped.resize((1280, 720), Image.Resampling.LANCZOS)

                cropped.save(path, format='JPEG', quality=88, optimize=True, progressive=True)
        except Exception:
            return

        type(self).objects.filter(pk=self.pk).update(
            image_crop_x=None,
            image_crop_y=None,
            image_crop_w=None,
            image_crop_h=None,
        )

    def clean(self):
        super().clean()

        # Só exige campos obrigatórios quando for PUBLICAR.
        # Em rascunho/revisão/agendado, pode salvar incompleto.
        if self.status == 'published':
            errors = {}

            if not (self.title or '').strip():
                errors['title'] = 'Informe um título para publicar.'

            # Imagem destacada: garante um mínimo de qualidade para os cards (tipo portal).
            # Não bloqueia rascunho; só exige ao publicar.
            if self.image:
                try:
                    w = int(getattr(self.image, 'width', 0) or 0)
                    h = int(getattr(self.image, 'height', 0) or 0)
                except Exception:
                    w = h = 0
                # 16:9 recomendado (ex.: 1280x720). Aqui usamos um mínimo mais tolerante.
                if w and h and (w < 960 or h < 540):
                    errors['image'] = (
                        'Imagem destacada muito pequena. Recomendo pelo menos 960×540 (ideal: 1280×720) '
                        'para não ficar pixelada nos destaques.'
                    )

            # Se não tiver slug, gera a partir do título.
            if not (self.slug or '').strip() and (self.title or '').strip():
                base = slugify(self.title) or 'post'
                candidate = base
                i = 2
                while Post.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                    candidate = f"{base}-{i}"
                    i += 1
                self.slug = candidate

            if errors:
                raise ValidationError(errors)


class PendingAuthor(User):
    class Meta:
        proxy = True
        verbose_name = "Autor pendente"
        verbose_name_plural = "Pendentes de aprovação"


class PageView(models.Model):
    KIND_CHOICES = (
        ('post', 'Post'),
        ('home', 'Home'),
        ('category', 'Categoria'),
        ('author', 'Autor'),
    )

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)

    # Referências (preenchidas conforme o tipo)
    post = models.ForeignKey('Post', null=True, blank=True, on_delete=models.SET_NULL, related_name='pageviews')
    author = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='author_pageviews')
    category = models.ForeignKey('Category', null=True, blank=True, on_delete=models.SET_NULL, related_name='pageviews')

    # Privacidade: não salva IP. Usa um identificador derivado da sessão para estimar "únicos".
    session_hash = models.CharField(max_length=64, blank=True, db_index=True)

    # Contexto leve (opcional)
    referrer = models.URLField(blank=True)
    ref_domain = models.CharField(max_length=255, blank=True, db_index=True)
    user_agent = models.CharField(max_length=255, blank=True)

    source_type = models.CharField(
        max_length=20,
        blank=True,
        db_index=True,
        help_text="direct | search | social | referral | utm",
    )
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=150, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at', 'kind']),
            models.Index(fields=['post', 'created_at']),
        ]

    def __str__(self):
        return f"{self.kind} @ {self.created_at:%Y-%m-%d %H:%M}"


class EngagementEvent(models.Model):
    EVENT_CHOICES = (
        ('time', 'Tempo na página (segundos)'),
        ('scroll', 'Scroll máximo (%)'),
    )

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    post = models.ForeignKey('Post', null=True, blank=True, on_delete=models.SET_NULL, related_name='engagement_events')
    session_hash = models.CharField(max_length=64, blank=True, db_index=True)

    event = models.CharField(max_length=20, choices=EVENT_CHOICES, db_index=True)
    value_int = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['created_at', 'event']),
            models.Index(fields=['post', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event}={self.value_int}"


class LinkClick(models.Model):
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    post = models.ForeignKey('Post', null=True, blank=True, on_delete=models.SET_NULL, related_name='linkclicks')
    url = models.URLField(max_length=1000)
    session_hash = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at', 'post']),
        ]

    def __str__(self):
        return f"Click {self.url}"
