from django.urls import path
from . import views

urlpatterns = [
    path('', views.post_list, name='post_list'),
    path('cadastro/', views.author_signup, name='author_signup'),
    path('metrics/click/', views.metrics_link_click, name='metrics_link_click'),
    path('metrics/engagement/', views.metrics_engagement, name='metrics_engagement'),
    path('categoria/<slug:slug>/', views.category_list, name='category_list'),
    path('autor/<str:username>/', views.author_detail, name='author_detail'),
    path('<slug:slug>/', views.post_detail, name='post_detail'),
]