from django.contrib import admin
from .models import User, Connection, Message

class ConnectionAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'accepted', 'created_date', 'updated_date')

class MessageAdmin(admin.ModelAdmin):
    list_display = ('connection', 'user', 'text', 'created')

admin.site.register(User)
admin.site.register(Connection, ConnectionAdmin)
admin.site.register(Message, MessageAdmin)
# Register your models here.
