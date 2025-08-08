from rest_framework import serializers
from .models import Message

class MessageSerializer(serializers.ModelSerializer):   
    # add a extra field to the serializer named voice_url which is not a model field

    voice_url = serializers.SerializerMethodField()
    class Meta:
        model = Message
        fields = ['id', 'sender', 'text', 'voice_url', 'voice_message', 'timestamp', 'reaction']

    
    def get_voice_url(self, obj):
        # if the message is a voice message return the voice message url
        if obj.voice_message:
            return obj.voice_message.url
        return None
        
    