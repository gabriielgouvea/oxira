from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from ckeditor_uploader.fields import RichTextUploadingField
from django.db.models.signals import post_save
from django.dispatch import receiver

# Perfil do Usuário (Avatar, Bio, etc)
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Foto de Perfil")
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

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

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

    title = models.CharField(max_length=200, verbose_name="Título")
    subtitle = models.CharField(max_length=255, blank=True, verbose_name="Subtítulo")
    slug = models.SlugField(unique=True, help_text="URL amigável gerada automaticamente")
    
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts', verbose_name="Autor")
    
    # Conteúdo e Mídia
    content = RichTextUploadingField(verbose_name="Conteúdo")
    image = models.ImageField(upload_to='posts/', blank=True, null=True, verbose_name="Imagem Destacada")
    
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
        return self.title


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
