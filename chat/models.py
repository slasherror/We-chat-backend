
# Create your models here.
from django.contrib.auth.models import User
from django.db import models
import base64

class KeyPair(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    public_key = models.TextField()
    private_key = models.TextField()
class Chat(models.Model):
    participants = models.ManyToManyField(User, related_name="chats")
    public_key = models.TextField(null=True)
    private_key = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Message(models.Model):
    chat = models.ForeignKey(Chat, related_name="messages", on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    voice_message = models.FileField(upload_to="voice_messages/", blank=True, null=True)
    encrypted_audio = models.BinaryField(blank=True, null=True)  # To store the encrypted audio
    encrypted_aes_key = models.BinaryField(blank=True, null=True)  # RSA-encrypted AES key
    reaction = models.CharField(max_length=8, blank=True, null=True)  # Emoji or reaction string
    timestamp = models.DateTimeField(auto_now_add=True)

    def encrypted_audio_length(self):
        if self.encrypted_audio:
            return f"{len(self.encrypted_audio)} bytes"
        return "No audio"

    def encrypted_audio_base64(self):
        if self.encrypted_audio:
            return base64.b64encode(self.encrypted_audio).decode('utf-8')
        return "No audio"

    encrypted_audio_length.short_description = 'Audio Length'
    encrypted_audio_base64.short_description = 'Base64 Encoded Audio'


