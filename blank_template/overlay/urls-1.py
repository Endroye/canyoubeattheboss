 from django.urls import path
from .views import overlay_data

urlpatterns = [
    path('overlay/', overlay_data, name='overlay'),
]
