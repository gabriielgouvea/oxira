from django.db import models
from django.core.cache import cache

class AdConfig(models.Model):
    # Classe Singleton para armazenar configurações de anúncios
    publisher_id = models.CharField(
        max_length=100, 
        verbose_name="ID do Publicador (Publisher ID)",
        help_text="Exemplo: ca-pub-1234567890123456. Você encontra isso no topo da página ao fazer login no Google AdSense."
    )
    
    active = models.BooleanField(
        default=True, 
        verbose_name="Ativar Anúncios",
        help_text="Desmarque para remover todos os anúncios do site temporariamente."
    )

    in_article_slot_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="ID do Bloco: Dentro da Matéria",
        help_text="Crie um bloco 'In-article' no AdSense e cole o 'data-ad-slot' aqui. Se vazio, o botão de anúncio não funcionará."
    )

    def save(self, *args, **kwargs):
        self.pk = 1 # Garante que só exista 1 registro
        super().save(*args, **kwargs)
        cache.delete('ad_config') # Limpa cache

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    class Meta:
        verbose_name = "Configuração de Publicidade (AdSense)"
        verbose_name_plural = "Configuração de Publicidade (AdSense)"
