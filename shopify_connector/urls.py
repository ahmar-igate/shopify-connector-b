from django.urls import path, include
from app import views

urlpatterns = [
    path('sconnector/', views.default, name='index'),
    path('sconnector/api/', include('app.urls')),
]
