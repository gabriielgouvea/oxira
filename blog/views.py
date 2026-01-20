from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpRequest
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import AuthorSignupForm
from .metrics import get_session_hash, is_safe_http_url, record_post_view
from .models import Category, EngagementEvent, LinkClick, Post, UserProfile

def post_list(request):
    posts = Post.objects.filter(status='published').order_by('-published_date')
    return render(request, 'blog/post_list.html', {'posts': posts})

def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, status='published')

    # Métrica: view do post
    record_post_view(request, post)

    try:
        author_profile = post.author.profile
    except UserProfile.DoesNotExist:
        author_profile = None

    more_from_author = (
        Post.objects.filter(status='published', author=post.author)
        .exclude(pk=post.pk)
        .order_by('-published_date')[:5]
    )
    return render(
        request,
        'blog/post_detail.html',
        {'post': post, 'author_profile': author_profile, 'more_from_author': more_from_author},
    )


@csrf_exempt
@require_POST
def metrics_link_click(request: HttpRequest):
    # Proteção simples contra POSTs externos
    host = (request.get_host() or '').lower()
    origin = (request.headers.get('Origin') or '').lower()
    ref = (request.headers.get('Referer') or '').lower()
    if origin and host not in origin:
        return JsonResponse({'ok': False}, status=400)
    if ref and host not in ref:
        return JsonResponse({'ok': False}, status=400)

    url = (request.POST.get('url') or '').strip()
    if not url or len(url) > 1000 or not is_safe_http_url(url):
        return JsonResponse({'ok': False}, status=400)

    post_id = request.POST.get('post_id')
    post = None
    if post_id and str(post_id).isdigit():
        post = Post.objects.filter(pk=int(post_id)).only('id').first()

    LinkClick.objects.create(
        post=post,
        url=url,
        session_hash=get_session_hash(request),
    )
    return JsonResponse({'ok': True})


@csrf_exempt
@require_POST
def metrics_engagement(request: HttpRequest):
    host = (request.get_host() or '').lower()
    origin = (request.headers.get('Origin') or '').lower()
    ref = (request.headers.get('Referer') or '').lower()
    if origin and host not in origin:
        return JsonResponse({'ok': False}, status=400)
    if ref and host not in ref:
        return JsonResponse({'ok': False}, status=400)

    event = (request.POST.get('event') or '').strip().lower()
    if event not in {'time', 'scroll'}:
        return JsonResponse({'ok': False}, status=400)

    value = request.POST.get('value')
    try:
        value_int = int(value)
    except Exception:
        return JsonResponse({'ok': False}, status=400)

    # limites
    if event == 'time':
        value_int = max(0, min(600, value_int))
    else:
        value_int = max(0, min(100, value_int))

    post_id = request.POST.get('post_id')
    post = None
    if post_id and str(post_id).isdigit():
        post = Post.objects.filter(pk=int(post_id)).only('id').first()

    EngagementEvent.objects.create(
        post=post,
        event=event,
        value_int=value_int,
        session_hash=get_session_hash(request),
    )
    return JsonResponse({'ok': True})

def category_list(request, slug):
    category = get_object_or_404(Category, slug=slug)
    posts = Post.objects.filter(status='published', category=category).order_by('-published_date')
    return render(request, 'blog/post_list.html', {'posts': posts, 'category': category})


def author_detail(request, username):
    User = get_user_model()
    author = get_object_or_404(User.objects.select_related('profile'), username=username)

    try:
        profile = author.profile
    except UserProfile.DoesNotExist:
        profile = None

    posts_qs = Post.objects.filter(status='published', author=author).order_by('-published_date')
    posts_count = posts_qs.count()
    paginator = Paginator(posts_qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    role_label = 'Autor'
    if profile and getattr(profile, 'role', None) == 'author':
        role_label = 'Repórter'
    elif profile and getattr(profile, 'role', None) == 'admin':
        role_label = 'Editor'

    return render(
        request,
        'blog/author_detail.html',
        {
            'author': author,
            'profile': profile,
            'role_label': role_label,
            'page_obj': page_obj,
            'posts': page_obj.object_list,
            'posts_count': posts_count,
        },
    )


@transaction.atomic
def author_signup(request: HttpRequest):
    if request.method != 'POST':
        return redirect('admin:login')

    form = AuthorSignupForm(request.POST, request.FILES)
    if not form.is_valid():
        # Re-render a tela de login do admin, já com erros do cadastro
        from django.contrib.auth.forms import AuthenticationForm

        login_form = AuthenticationForm(request)
        return render(request, 'admin/login.html', {'form': login_form, 'signup_form': form})

    user = form.save(commit=False)
    user.email = form.cleaned_data['email']
    user.first_name = form.cleaned_data['first_name']
    user.last_name = form.cleaned_data.get('last_name') or ''
    user.is_active = False
    user.is_staff = False
    user.is_superuser = False
    user.save()
    form.save_m2m()

    profile = user.profile
    profile.role = 'author'
    profile.cpf = form.cleaned_data.get('cpf')
    profile.phone = form.cleaned_data.get('phone')
    profile.instagram = form.cleaned_data.get('instagram')
    profile.bio = form.cleaned_data.get('bio')
    avatar = form.cleaned_data.get('avatar')
    if avatar:
        profile.avatar = avatar
    profile.save()

    messages.success(request, 'Cadastro enviado para aprovação. Assim que for aprovado, você poderá acessar o painel.')
    return redirect('admin:login')
