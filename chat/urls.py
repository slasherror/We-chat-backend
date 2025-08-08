from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import search_users, start_chat, get_chat_messages, get_chats, transcribe_audio, auto_reply, tts_voice, set_message_reaction
urlpatterns = [

    path("chats/", get_chats, name="get_chats"),
    path("search_users/", search_users, name="search_users"),
    
    path("start_chat/", start_chat, name="start_chat"),



    path("<int:chat_id>/messages/", get_chat_messages, name="get_chat_messages"),
    
    path('transcribe/', transcribe_audio, name='transcribe_audio'),
    
    path('auto-reply/', auto_reply, name='auto_reply'),

    path('tts/', tts_voice, name='tts_voice'),

    path('set_message_reaction/', set_message_reaction, name='set_message_reaction'),


]
