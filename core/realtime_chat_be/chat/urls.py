from django.urls import path
from .views import Login, Signup

urlpatterns = [
    path('login/', Login.as_view()),
    path('signup/', Signup.as_view())
]