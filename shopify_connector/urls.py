from django.urls import path, include
from app import views
from django.conf import settings
from  django.conf.urls.static import static 

urlpatterns = [
    path('sconnector/', views.default, name='index'),
    path('sconnector/api/', include('app.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root = settings.STATIC_URL)