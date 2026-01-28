from django import template
from django.utils.safestring import mark_safe
from blog.models_ads import AdConfig

register = template.Library()

@register.simple_tag
def get_ad_config():
    # Retorna a configuração global para usar no base.html (head)
    try:
        config = AdConfig.load()
        if config.active and config.publisher_id:
            return config
    except:
        pass
    return None

@register.filter
def inject_ads(content):
    # Substitui os marcadores do CKEditor pelo código real do AdSense
    try:
        config = AdConfig.load()
        if not config.active or not config.publisher_id:
            # Se desativado, remove o marcador para não ficar feio
            return content.replace('<div class="oxira-ad-marker" style="background:#f8f9fa; border:2px dashed #dee2e6; color:#6c757d; padding:15px; text-align:center; font-weight:bold; margin:20px 0; user-select:none;">--- PUBLICIDADE ---</div>', '')
            
        # Código do Bloco In-Article
        # Se o usuário configurou um slot específico, usamos ele.
        # Caso contrário, usamos um bloco genérico ou alertamos no console.
        slot_id = config.in_article_slot_id
        
        if slot_id:
            ad_code = f"""
            <div style="margin: 20px 0; text-align: center;">
                <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={config.publisher_id}"
                     crossorigin="anonymous"></script>
                <ins class="adsbygoogle"
                     style="display:block; text-align:center;"
                     data-ad-layout="in-article"
                     data-ad-format="fluid"
                     data-ad-client="{config.publisher_id}"
                     data-ad-slot="{slot_id}"></ins>
                <script>
                     (adsbygoogle = window.adsbygoogle || []).push({{}});
                </script>
            </div>
            """
        else:
            # Fallback: Se não tem slot configurado, o Google Auto Ads deve cuidar disso,
            # mas vamos remover o marcador visual.
             return content.replace('<div class="oxira-ad-marker" style="background:#f8f9fa; border:2px dashed #dee2e6; color:#6c757d; padding:15px; text-align:center; font-weight:bold; margin:20px 0; user-select:none;">--- PUBLICIDADE ---</div>', '')

        # O marcador exato inserido pelo plugin.js
        marker = '<div class="oxira-ad-marker" style="background:#f8f9fa; border:2px dashed #dee2e6; color:#6c757d; padding:15px; text-align:center; font-weight:bold; margin:20px 0; user-select:none;">--- PUBLICIDADE ---</div>'
        
        return mark_safe(content.replace(marker, ad_code))
        
    except Exception:
        return content
