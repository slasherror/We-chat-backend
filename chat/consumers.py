from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
import json
from .models import Chat, Message, KeyPair
from chat.utils import encrypt_message, decrypt_final_audio, encrypt_final_audio
from base64 import b64decode, b64encode

# ✅ Global presence tracker
ONLINE_USERS = {}

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.chat_group_name = f'chat_{self.chat_id}'
        self.presence_group = "presence_room"

        self.user = self.scope["user"]
        self.user_id = self.user.id

        await self.accept()  # ✅ Accept the WebSocket first!

        await self.channel_layer.group_add(self.chat_group_name, self.channel_name)
        await self.channel_layer.group_add(self.presence_group, self.channel_name)

        # ✅ Mark user as online
        ONLINE_USERS[self.user_id] = self.channel_name

        # ✅ Send list of all online users to the current user
        print(f"User {self.user_id} connected. Online users: {list(ONLINE_USERS.keys())}")
        await self.send(text_data=json.dumps({
            "type": "initial-online-list",
            "user_ids": list(ONLINE_USERS.keys())
        }))

        # ✅ Notify others about your presence
        await self.broadcast_user_status(online=True)



    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.chat_group_name, self.channel_name)
        await self.channel_layer.group_discard(self.presence_group, self.channel_name)

        if self.user_id in ONLINE_USERS:
            print(f"User {self.user_id} disconnected")
            del ONLINE_USERS[self.user_id]
            await self.broadcast_user_status(online=False)



    async def broadcast_user_status(self, online):
        await self.channel_layer.group_send(
            self.presence_group,
            {
                "type": "user_status",
                "user_id": self.user_id,
                "online": online
            }
        )

    async def user_status(self, event):
        print(f"Broadcasting user status: {event['user_id']} is {event['online']}")
        await self.send(text_data=json.dumps({
            "type": "user-status",
            "userId": event["user_id"],
            "online": event["online"]
        }))

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

        elif event_type == "message":
            # Client now sends ciphertext already encrypted with chat public key
            encrypted_message = data["message"]
            sender_id = self.scope["user"].id
            recipient_id = data["recipient"]

            sender = await database_sync_to_async(User.objects.get)(id=sender_id)

            new_message = await database_sync_to_async(Message.objects.create)(
                chat=chat,
                sender=sender,
                text=encrypted_message
            )

            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    "type": "chat_message",
                    "id": new_message.id,
                    "message": encrypted_message,
                    "sender": sender.id,
                    "recipient": recipient_id,
                }
            )

        elif event_type == "voice":
            sender_id = self.scope["user"].id
            recipient_id = data["recipient"]

            # Client sends encrypted payloads as base64 strings
            encrypted_audio_b64 = data.get("encrypted_audio")
            encrypted_aes_key_b64 = data.get("encrypted_aes_key")

            if not (encrypted_audio_b64 and encrypted_aes_key_b64):
                # Ignore malformed voice event
                return

            encrypted_audio = b64decode(encrypted_audio_b64)
            encrypted_aes_key = b64decode(encrypted_aes_key_b64)

            # Use static IV for all audio
            iv = b"ANIK@&01NAFIUL#$"

            sender = await database_sync_to_async(User.objects.get)(id=sender_id)

            message = await database_sync_to_async(Message.objects.create)(
                chat=chat,
                sender=sender,
                text="",
                encrypted_audio=encrypted_audio,
                encrypted_aes_key=encrypted_aes_key
            )

            # Broadcast encrypted payload as-is; clients will decrypt
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    'type': 'voice_messages',
                    'id': message.id,
                    'sender': sender_id,
                    'recipient': recipient_id,
                    'encrypted_audio': encrypted_audio_b64,
                    'encrypted_aes_key': encrypted_aes_key_b64,
                    # Do NOT send IV
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
        await self.send(text_data=json.dumps({
            "type": "message",
            "id": event["id"],
            "text": event["message"],  # ciphertext
            "voice_url": event.get("audio_url", ""),
            "sender": event["sender"],
        }))

    async def voice_messages(self, event):
        await self.send(text_data=json.dumps({
            "type": "voice_message",
            "id": event["id"],
            "text": "",
            "encrypted_audio": event["encrypted_audio"],
            "encrypted_aes_key": event["encrypted_aes_key"],
            # Do NOT send IV
            "sender": event["sender"],
        }))

    async def delete_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "delete",
            "id": event["id"],
            "message": event["message"],
            "sender": event["sender"],
        }))

    async def chat_typing(self, event):
        await self.send(text_data=json.dumps({
            "type": "typing",
            "is_typing": event["is_typing"],
            "sender": event["sender"],
        }))
