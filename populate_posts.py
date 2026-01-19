import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from django.contrib.auth.models import User
from blog.models import Category, Post
from django.utils import timezone
from django.utils.text import slugify

def populate():
    # Garantir usuario admin
    if User.objects.filter(username='admin').exists():
        user = User.objects.get(username='admin')
    else:
        user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')

    # Categorias e suas cores (vamos usar slugs para lógica de cor no template)
    categories_data = [
        'Oxira Esportes',
        'Oxira Empreendedorismo',
        'Oxira Política',
        'Oxira Alphaville'
    ]

    categories_objs = {}
    for cat_name in categories_data:
        slug = slugify(cat_name)
        cat, created = Category.objects.get_or_create(name=cat_name, defaults={'slug': slug})
        categories_objs[cat_name] = cat
        print(f'Categoria processada: {cat_name}')

    # Posts Genéricos
    posts_data = [
        {
            'title': 'O Futuro das Startups em 2026: Menos Hype, Mais Lucro',
            'category': 'Oxira Empreendedorismo',
            'content': 'O mercado mudou. Investidores não querem mais promessas de crescimento infinito sem base sólida. Em 2026, a palavra de ordem é eficiência operacional e EBITDA positivo desde o dia um. As empresas que sobreviveram ao inverno das startups agora colhem frutos, mas com uma mentalidade muito mais tradicional...',
            'status': 'published'
        },
        {
            'title': 'Final do Campeonato: A Tática que Mudou o Jogo',
            'category': 'Oxira Esportes',
            'content': 'Não foi apenas sorte. A análise tática detalhada mostra como a mudança aos 30 minutos do segundo tempo desestabilizou a defesa adversária. O uso de alas invertidos e a pressão alta forçaram erros que resultaram na virada histórica que vimos ontem...',
            'status': 'published'
        },
        {
            'title': 'Nova Lei de Zoneamento em Pauta no Congresso',
            'category': 'Oxira Política',
            'content': 'Debates acalorados marcam a sessão desta terça-feira. A proposta visa modernizar as regras de ocupação urbana, mas enfrenta resistência de grupos ambientalistas e setor imobiliário. Entenda os principais pontos de divergência e como isso afeta o seu dia a dia na cidade...',
            'status': 'published'
        },
        {
            'title': 'Alphaville Recebe Novo Centro Gastronômico de Luxo',
            'category': 'Oxira Alphaville',
            'content': 'A região ganha mais uma opção de alta gastronomia. Com investimento milionário, o novo complexo promete reunir chefs renomados e experiências exclusivas para os moradores. Visitamos o local antes da inauguração e contamos tudo o que você pode esperar...',
            'status': 'published'
        },
        {
            'title': 'IA no Varejo: Como a Tecnologia Está Personalizando o Consumo',
            'category': 'Oxira Empreendedorismo',
            'content': 'Não é mais ficção científica. Lojas físicas estão usando câmeras inteligentes e algoritmos preditivos para oferecer ofertas em tempo real. Entrevistamos especialistas que mostram como a privacidade dos dados convive com a conveniência extrema...',
            'status': 'published'
        },
        {
            'title': 'O Impacto das Olimpíadas no Desenvolvimento de Novos Atletas',
            'category': 'Oxira Esportes',
            'content': 'O ciclo olímpico se encerra, mas o legado permanece? Analisamos os números do investimento na base e conversamos com treinadores que alertam: sem apoio contínuo, as medalhas de hoje não garantem o pódio de amanhã...',
            'status': 'published'
        }
    ]

    for post_data in posts_data:
        cat = categories_objs[post_data['category']]
        base_slug = slugify(post_data['title'])
        slug = base_slug
        counter = 1
        while Post.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        Post.objects.get_or_create(
            title=post_data['title'],
            defaults={
                'slug': slug,
                'author': user,
                'category': cat,
                'content': post_data['content'],
                'status': post_data['status'],
                'published_date': timezone.now()
            }
        )
        print(f"Post criado: {post_data['title']}")

if __name__ == '__main__':
    populate()
