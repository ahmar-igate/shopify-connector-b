from django.urls import path
from .views import download_data

urlpatterns = [
    path('download/', download_data, name='download_data'),
]
