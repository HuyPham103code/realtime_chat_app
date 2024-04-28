from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path('chat/', consumers.ChatComsumer.as_asgi())
]