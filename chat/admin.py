from django.contrib import admin

# Register your models here.

from .models import Chat, Message, KeyPair

admin.site.register(Chat)

class KeyPairAdmin(admin.ModelAdmin):
    list_display = ['user', 'public_key', 'private_key']
    list_filter = ['user']
    search_fields = ['user']

admin.site.register(KeyPair, KeyPairAdmin)

# show the message model in the admin panel and show all the fields in the message model
class MessageAdmin(admin.ModelAdmin):
    list_display = ['chat', 'sender','encrypted_aes_key', 'encrypted_audio_length', 'timestamp']

    list_filter = ['chat', 'sender', 'timestamp']
    search_fields = ['chat', 'sender']
    readonly_fields = ('encrypted_audio_base64',)

admin.site.register(Message, MessageAdmin)