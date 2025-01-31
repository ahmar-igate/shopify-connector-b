from django.urls import path
from app import views

urlpatterns = [
    # path('fetch/', fetch_data, name='fetch'),
    # path('sync_data/', sync_data, name='sync_data'),
    # path("test/", save_orders, name="test"),
    # path("testsync/", testsync, name="testsync"),
    path('save/', views.fetch_data_shopify.as_view(), name='save'),
    path('sync/', views.sync_data.as_view(), name='sync'),
    
]
