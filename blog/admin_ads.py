from django.contrib import admin
from .models_ads import AdConfig

@admin.register(AdConfig)
class AdConfigAdmin(admin.ModelAdmin):
    # Garante que seja um "Singleton" no Admin (só pode editar, não criar vários)
    
    def has_add_permission(self, request):
        # Se já existe 1, não deixa criar outro
        if AdConfig.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Não deixa deletar a configuração, apenas desativar
        return False

    fieldsets = (
        ('Configuração Principal (Auto Ads)', {
            'description': 'Para ativar anúncios automáticos (Topo, Rodapé, Lateral), basta preencher abaixo. O Google decide onde mostrar.',
            'fields': ('publisher_id', 'active')
        }),
        ('Anúncio Manual (Dentro do Texto)', {
            'description': 'Configuração para o bloco que aparece quando você clica no botão "Anúncio" dentro do editor da matéria.',
            'fields': ('in_article_slot_id',)
        }),
    )
    
    list_display = ('publisher_id', 'active', 'in_article_slot_id')
