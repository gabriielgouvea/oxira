from django.urls import path
from . import views

urlpatterns = [
    path('', views.post_list, name='post_list'),
    path('consultas/', views.consultas, name='consultas'),
    path('preview/<int:pk>/', views.post_preview, name='post_preview'),
    path('preview/draft/set/', views.post_preview_draft_set, name='post_preview_draft_set'),
    path('preview/draft/<uuid:token>/', views.post_preview_draft, name='post_preview_draft'),
    path('api/consultas/fx/latest/', views.api_consultas_fx_latest, name='api_consultas_fx_latest'),
    path('api/consultas/fx/range/', views.api_consultas_fx_range, name='api_consultas_fx_range'),
    path('api/consultas/crypto/prices/', views.api_consultas_crypto_prices, name='api_consultas_crypto_prices'),
    path('api/consultas/crypto/chart/', views.api_consultas_crypto_chart, name='api_consultas_crypto_chart'),
    path('api/consultas/holidays/today/', views.api_consultas_holidays_today, name='api_consultas_holidays_today'),
    path('api/consultas/dayfacts/today/', views.api_consultas_dayfacts_today, name='api_consultas_dayfacts_today'),
    path('cadastro/', views.author_signup, name='author_signup'),
    path('metrics/click/', views.metrics_link_click, name='metrics_link_click'),
    path('metrics/engagement/', views.metrics_engagement, name='metrics_engagement'),
    path('categoria/<slug:slug>/', views.category_list, name='category_list'),
    path('autor/<str:username>/', views.author_detail, name='author_detail'),
    path('<slug:slug>/', views.post_detail, name='post_detail'),
]