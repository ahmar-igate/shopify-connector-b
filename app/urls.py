from django.urls import path
from .views import fetch_data, sync_data

urlpatterns = [
    path('fetch/', fetch_data, name='fetch'),
    path('sync_data/', sync_data, name='sync_data'),
]
