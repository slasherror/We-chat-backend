from channels.generic.websocket import AsyncWebsocketConsumer
import json
from .models import Chat, Message, KeyPair
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.PublicKey import RSA
import base64
from chat.utils import encrypt_message, decrypt_final_audio, encrypt_final_audio
import io
from Crypto.Random import get_random_bytes
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
import os
from asgiref.sync import async_to_sync

from Crypto.Util.Padding import pad
from base64 import b64encode, b64decode


class ChatConsumer(AsyncWebsocketConsumer):
   
    async def connect(self):
  
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        # print("Self : ",self.scope)
        self.chat_group_name = f'chat_{self.chat_id}'
        await self.channel_layer.group_add(self.chat_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.chat_group_name,
            self.channel_name
        )
    
  

    async def get_user_by_email(self, email):
        return await User.objects.get(email=email)

    async def receive(self, text_data):

        data = json.loads(text_data)
        event_type = data["type"]
        chat = await database_sync_to_async(Chat.objects.get)(id=self.chat_id)

        if event_type == "delete":
            message_id = data["message_id"]
            sender_id = data["sender"]
            message = await database_sync_to_async(Message.objects.get)(id=message_id)
            await database_sync_to_async(message.delete)()
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    "type": "delete_message",
                    "id": message_id,
                    "message": "This message has been deleted",
                    "sender": sender_id,
                }
            )
       
        if event_type == "message":
        
            message = data["message"]
            sender_id = self.scope["user"].id
            recipient_id = data["recipient"]

            # print(sender_id)
            # Fetch the chat and sender asynchronously
            chat = await database_sync_to_async(Chat.objects.get)(id=self.chat_id)
            sender = await database_sync_to_async(User.objects.get)(id=sender_id)

            # public_key = await database_sync_to_async(KeyPair.objects.get)(user=recipient_id)
            # public_key = public_key.public_key

            encrypted_message = encrypt_message(chat.public_key, message)



            # Store encrypted message in database
            new_message = await database_sync_to_async(Message.objects.create)(
                chat=chat,
                sender=sender,
                text=encrypted_message
           
            )


            # Send the message to the WebSocket group
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    "type": "chat_message",
                    "id": new_message.id,
                    "message": message,
                    "sender": sender.id,
                    "recipient": recipient_id,
                }
            )

        elif event_type == "voice":
            # complete the code here
            sender_id = self.scope["user"].id
   
            audio_data = b64decode(data["voice"])  # base64-decoded audio blob
            recipient_id = data["recipient"]
            sender = await database_sync_to_async(User.objects.get)(id=sender_id)
            chat = await database_sync_to_async(Chat.objects.get)(id=self.chat_id)
            
            
            encrypted_audio, encrypted_aes_key, iv = encrypt_final_audio(audio_data, chat.public_key)

            # Save the encrypted audio file to the database
            message = await database_sync_to_async(Message.objects.create)(
                chat=chat,
                sender=sender,
                text="",
                encrypted_audio=encrypted_audio,
                encrypted_aes_key=encrypted_aes_key,
                iv=iv
            )


            decrypted_audio = decrypt_final_audio(encrypted_audio,encrypted_aes_key,iv,chat.private_key)




            # Send back the audio URL for instant playback
            await self.channel_layer.group_send(
                self.chat_group_name,
                {   
                    'type': 'voice_messages',
                    'id': message.id,
                    'sender': sender_id,
                    'message':'',
                    'recipient': recipient_id,
                    'audio': decrypted_audio,
               
                }
            )



        elif event_type == "typing":
            typing_status = data["is_typing"]
            sender = self.scope["user"].username
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    "type": "chat_typing",
                    "is_typing": typing_status,
                    "sender": sender,
                }
            )


    async def chat_message(self, event):
        message = event["message"]
        sender = event["sender"]
        voice_message = event.get("audio_url", "")
        

        await self.send(text_data=json.dumps({
            "type": "message",
            "id": event["id"],
            "text": message,
            "voice_url": voice_message,
            "sender": sender,
        }))

    async def chat_typing(self, event):
        is_typing = event["is_typing"]
        sender = event["sender"]

        await self.send(text_data=json.dumps({
            "type": "typing",
            "is_typing": is_typing,
            "sender": sender,
        }))

    async def voice_messages(self, event):
 
        sender = event["sender"]

        await self.send(text_data=json.dumps({

            "type": "voice_message",
            "id": event["id"],
            "text": "",
            "audio": event["audio"],
   
            "sender": sender,
        }))
    
    async def delete_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "delete",
            "id": event["id"],
            "message": event["message"],
            "sender": event["sender"],
        }))