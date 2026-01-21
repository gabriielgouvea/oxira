from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from .models import Post, Category, UserProfile, PendingAuthor
from django.utils.html import format_html
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.admin.views.main import ChangeList

from django.forms import CheckboxSelectMultiple
from django.db import models
from django import forms


def _profile(user):
    return getattr(user, 'profile', None)


def _is_admin(user):
    p = _profile(user)
    return bool(user.is_superuser or (p and p.role == 'admin'))


def _is_author(user):
    p = _profile(user)
    return bool(p and p.role == 'author')

# Inline para editar o perfil dentro do usuário
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Dados do Autor'
    
    # Widget de Checkbox para as Categorias
    formfield_overrides = {
        models.ManyToManyField: {'widget': CheckboxSelectMultiple},
    }
    
    fieldsets = (
        (None, {
            'fields': (
                'role',
                'allowed_categories',
                'cpf',
                'phone',
                'website',
                'instagram',
                'twitter',
                'linkedin',
                'facebook',
                'cep',
                'address',
                'number',
                'complement',
                'neighborhood',
                'city',
                'state',
                'avatar',
                'bio',
            )
        }),
    )

# Definir a nova classe UserAdmin
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    
    # Customização da listagem
    list_display = ('username_display', 'get_avatar', 'full_name_display', 'email_display', 'phone_display', 'get_role', 'get_post_count')
    list_select_related = ('profile',)
    
    # Busca poderosa
    search_fields = ('username', 'first_name', 'last_name', 'email', 'profile__phone', 'profile__cpf')
    
    # CSS e JS Customizados
    class Media:
        js = (
            'admin/js/live_search.js',
            'admin/js/cep_lookup.js',
            'admin/js/user_password_cleanup.js',
            'admin/js/copy_reset_link.js',
        )
        css = {
            'all': (
                'admin/css/clean_users.css',
                'admin/css/onepage_form.css',
            )
        }

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}

        if object_id:
            user_obj = self.get_object(request, object_id)
            if user_obj is not None:
                uidb64 = urlsafe_base64_encode(force_bytes(user_obj.pk))
                token = default_token_generator.make_token(user_obj)
                reset_path = reverse('password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
                extra_context['oxira_reset_link'] = request.build_absolute_uri(reset_path)
                extra_context['oxira_admin_password_url'] = reverse('admin:auth_user_password_change', args=[user_obj.pk])

        return super().changeform_view(request, object_id, form_url, extra_context=extra_context)

    # UMA PÁGINA SÓ, sem blocos/títulos: tudo em coluna única
    save_on_top = False
    fieldsets = (
        (None, {
            'fields': (
                'username',
                'password',
                'first_name',
                'last_name',
                'email',
                'is_active',
            )
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'first_name', 'last_name', 'email', 'is_active'),
        }),
    )

    # Sem filtros laterais e sem ações em massa
    list_filter = ()
    actions = None
    list_display_links = ('username_display', 'get_avatar')

    # Remove completamente a parte de grupos/permissões do Django (aquela lista enorme)
    filter_horizontal = ()

    def get_form(self, request, obj=None, **kwargs):
        # Remover campos avançados do form, caso apareçam por herança
        self.exclude = ('groups', 'user_permissions', 'is_staff', 'is_superuser', 'last_login', 'date_joined')
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        # Sempre permite login no admin
        obj.is_staff = True
        if obj.is_active is None:
            obj.is_active = True
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        user = form.instance
        p = _profile(user)
        if not p:
            return

        # Regra simples: role=admin => superuser; role=author => não-superuser
        if p.role == 'admin':
            user.is_staff = True
            user.is_superuser = True
        else:
            user.is_staff = True
            user.is_superuser = False
        user.save(update_fields=['is_staff', 'is_superuser'])
    
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        # Mantém checkbox só para allowed_categories (o resto nem aparece)
        form_field = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name == 'allowed_categories':
            form_field.widget = CheckboxSelectMultiple()
        return form_field

    def email_display(self, obj):
        return obj.email
    email_display.short_description = "E-mail"
    email_display.admin_order_field = 'email'

    def phone_display(self, obj):
        return obj.profile.phone if hasattr(obj, 'profile') and obj.profile.phone else "-"
    phone_display.short_description = "Telefone"
    
    def username_display(self, obj):
        return obj.username
    username_display.short_description = 'Username'
    
    def full_name_display(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name_display.short_description = 'Nome'

    def get_avatar(self, obj):
        if hasattr(obj, 'profile') and obj.profile.avatar:
            return format_html(
                '<img src="{}" width="40" height="40" style="border-radius:50%; object-fit:cover;" />', 
                obj.profile.avatar.url
            )
        return format_html('<div style="width:40px;height:40px;background:#ddd;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#666;">{}</div>', obj.username[0].upper())
    get_avatar.short_description = 'Avatar'

    def get_role(self, obj):
        if _is_admin(obj):
            return format_html('<span class="badge badge-error">Administrador</span>')
        
        # Pega a role do perfil se existir
        if hasattr(obj, 'profile'):
            roles_map = {
                'admin': 'Administrador',
                'author': 'Autor',
            }
            role_display = roles_map.get(obj.profile.role, 'Usuário')
            
            colors_map = {
                'admin': 'badge-danger',
                'author': 'badge-success',
            }
            color = colors_map.get(obj.profile.role, 'badge-secondary')
            
            return format_html('<span class="badge {}">{}</span>', color, role_display)
            
        return "Usuário"
    get_role.short_description = 'Role'

    def get_post_count(self, obj):
        count = obj.blog_posts.count()
        return format_html('<strong style="font-size:1.2em;">{}</strong>', count)
    get_post_count.short_description = 'Posts'

# Desregistrar o User padrão e registrar o novo
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(PendingAuthor)
class PendingAuthorAdmin(UserAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_active=False, profile__role='author')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return _is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_admin(request.user)

    actions = ['approve_selected']

    @admin.action(description='Aprovar autores selecionados')
    def approve_selected(self, request, queryset):
        updated = queryset.update(is_active=True, is_staff=True)
        self.message_user(request, f'{updated} autor(es) aprovado(s).')

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    class Media:
        js = (
            'admin/js/live_search.js',
        )

    # Destaque na Listagem
    list_display = ('title_display', 'status_badge', 'author', 'category', 'published_date')
    list_filter = ()
    search_fields = ('title', 'content', 'subtitle', 'keywords')
    
    # Navegação por data
    date_hierarchy = None

    # Sem ações em massa (remove o seletor + botão "Ir")
    actions = None

    # Remove a ordenação nativa por clique nas colunas (setinhas, prioridade, "x")
    sortable_by = ()
    
    # Preenchimento automático de slug
    prepopulated_fields = {'slug': ('title',)}
    
    # Campos que usam ID (para performance se tiver muitos users)
    raw_id_fields = ('author',)

    class _PostChangeList(ChangeList):
        def get_filters_params(self, params=None):
            lookup_params = super().get_filters_params(params=params)
            lookup_params.pop('sort', None)
            return lookup_params

    def get_changelist(self, request, **kwargs):
        return self._PostChangeList

    def get_ordering(self, request):
        sort = (request.GET.get('sort') or '').strip()
        if sort == 'status':
            return ('status', '-published_date', '-created_date')
        if sort == 'author':
            return ('author__username', '-published_date', '-created_date')
        if sort == 'category':
            return ('category__name', '-published_date', '-created_date')
        if sort == 'published_asc':
            return ('published_date', 'created_date')
        if sort == 'published_desc':
            return ('-published_date', '-created_date')
        return super().get_ordering(request)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        # Deixa o autor pré-definido como o usuário logado.
        # Admin pode trocar; autor comum fica travado.
        if getattr(request, 'user', None) and request.user.is_authenticated:
            initial.setdefault('author', request.user.pk)
        return initial

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)

        # Para autores: mostra o campo, mas travado no próprio usuário.
        # Segurança real fica no save_model (que força author=request.user).
        if _is_author(request.user) and 'author' in form.base_fields:
            f = form.base_fields['author']
            f.queryset = User.objects.filter(pk=request.user.pk)
            f.initial = request.user.pk
            f.disabled = True
            # Evita UI de lookup do raw_id no caso de autores
            f.widget = forms.Select()

        # Para admin: também deixa pré-selecionado o próprio usuário (mas editável)
        if _is_admin(request.user) and 'author' in form.base_fields:
            form.base_fields['author'].initial = request.user.pk

        return form

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _is_admin(request.user):
            return qs
        if _is_author(request.user):
            return qs.filter(author=request.user)
        return qs.none()

    def has_view_permission(self, request, obj=None):
        if _is_admin(request.user):
            return True
        if _is_author(request.user):
            return obj is None or obj.author_id == request.user.id
        return False

    def has_change_permission(self, request, obj=None):
        if _is_admin(request.user):
            return True
        if _is_author(request.user):
            return obj is None or obj.author_id == request.user.id
        return False

    def has_delete_permission(self, request, obj=None):
        if _is_admin(request.user):
            return True
        if _is_author(request.user):
            return obj is None or obj.author_id == request.user.id
        return False

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        return ro

    def save_model(self, request, obj, form, change):
        # Autor sempre salva como ele mesmo
        if _is_author(request.user):
            obj.author = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Autor só pode escolher categoria dentre as permitidas
        if db_field.name == 'category' and _is_author(request.user):
            p = _profile(request.user)
            if p is not None:
                kwargs['queryset'] = p.allowed_categories.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    # Organização do Formulário de Edição
    fieldsets = (
        ('Identificação', {
            'fields': ('title', 'subtitle', 'slug', 'author')
        }),
        ('Conteúdo', {
            'fields': ('content', 'image', 'category')
        }),
        ('Controle Editorial', {
            'fields': ('status', 'published_date', 'internal_notes'),
            'classes': ('collapse',)
        }),
        ('Otimização para Buscas (SEO)', {
            'fields': ('meta_description', 'keywords'),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('created_date', 'updated_date'),
            'classes': ('collapse',),
            'description': 'Informações automáticas do sistema'
        })
    )
    
    readonly_fields = ('created_date', 'updated_date')
    
    # Métodos customizados para a Listagem (Badges coloridos)
    def status_badge(self, obj):
        colors = {
            'draft': 'warning',     # Amarelo
            'review': 'info',       # Azul
            'published': 'success', # Verde
            'scheduled': 'primary', # Roxo
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge badge-pill badge-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.allow_tags = True
    
    def title_display(self, obj):
        return format_html(
            '<strong>{}</strong><br><small class="text-muted">{}</small>',
            obj.title,
            obj.subtitle[:50] + "..." if obj.subtitle else ""
        )
    title_display.short_description = "Matéria"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'post_count')
    list_editable = ('order',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    
    def post_count(self, obj):
        return obj.posts.count()
    post_count.short_description = 'Qtd. Posts'

    def has_module_permission(self, request):
        return _is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_admin(request.user)

    def has_add_permission(self, request):
        return _is_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_admin(request.user)
