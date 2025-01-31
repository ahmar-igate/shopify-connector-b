from django.contrib import admin
from django.urls import path, include
from app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.default, name='index'),
    path('api/', include('app.urls')),
]
