from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Chat, Message, KeyPair
from .serializers import MessageSerializer
from chat.utils import generate_key_pair, decrypt_message, decrypt_final_audio, encrypt_message
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.http import HttpResponseNotFound, StreamingHttpResponse
import os
import uuid
from django.http import HttpResponse
import requests
from django.conf import settings
import base64
import tempfile
from rest_framework.permissions import IsAuthenticated
import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@api_view(["GET"])
def search_users(request):
    query = request.GET.get("email", "")
    users = User.objects.filter(email__icontains=query).exclude(id=request.user.id)
    results = [{"id": user.id, "email": user.email} for user in users]
    return Response(results)

@api_view(["POST"])
def start_chat(request):
    user_id = request.data.get("user_id")
    other_user = User.objects.get(id=user_id)
    chat = Chat.objects.filter(participants=request.user).filter(participants=other_user).first()

    if not chat:
        chat = Chat.objects.create()
        private_key, public_key = generate_key_pair()
        
        chat.participants.add(request.user, other_user)
        chat.private_key = private_key
        chat.public_key = public_key
        chat.save()
    elif not chat.public_key:
        private_key, public_key = generate_key_pair()
        chat.private_key = private_key
        chat.public_key = public_key
        chat.save()
    
    chat_data = {}
    chat_data["chat_id"] = chat.id
    chat_data["participants"] = [participant.id for participant in chat.participants.all()]
    chat_data['current_user'] = request.user.username
    chat_data['current_user_id'] = request.user.id
    chat_data['other_user'] = [participant.username for participant in chat.participants.all() if participant.username != request.user.username]
    return Response(chat_data)

@api_view(["GET"])
def get_chat_messages(request, chat_id):
    try:
        chat = Chat.objects.get(id=chat_id)
    except Chat.DoesNotExist:
        return Response({"error": "Chat not found."}, status=404)

    messages = Message.objects.filter(chat=chat).order_by("timestamp")
    private_key = chat.private_key

    decrypted_messages = []

    for message in messages:
        decrypted_text = ""
        decrypted_audio = None

        if message.text:
            decrypted_text = decrypt_message(private_key,message.text)

        if message.encrypted_aes_key:
            decrypted_audio = decrypt_final_audio(message.encrypted_audio, message.encrypted_aes_key, message.iv, private_key)

        decrypted_messages.append({
            "id": message.id,
            "sender": message.sender.id,
            "text": decrypted_text,
            "voice_url": decrypted_audio,  
            "timestamp": message.timestamp.isoformat(),
        })

    return Response(decrypted_messages, status=200)

@api_view(["GET"])
def get_chats(request):
    chats = Chat.objects.filter(participants=request.user)
    results = []
    for chat in chats:
        chat_data = {}
        chat_data["chat_id"] = chat.id
        chat_data["participants"] = [participant.id for participant in chat.participants.all()]
        chat_data['current_user'] = request.user.username
        chat_data['current_user_id'] = request.user.id
        chat_data['other_user'] = [participant.username for participant in chat.participants.all() if participant.username != request.user.username]
        chat_data["public_key"] = chat.public_key
        chat_data["private_key"] = chat.private_key
        results.append(chat_data)
    return Response(results)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def transcribe_audio(request):
    try:
        audio_data = request.data.get('audio')
        if not audio_data:
            return Response({'error': 'No audio data provided'}, status=400)
            
        # Decode base64 audio data
        audio_bytes = base64.b64decode(audio_data)
        
        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
            temp_audio.write(audio_bytes)
            temp_audio_path = temp_audio.name
            
        try:
            # Prepare the API request for OpenAI Whisper
            headers = {
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            }
            
            # Open and read the file in a separate block to ensure it's closed
            with open(temp_audio_path, 'rb') as audio_file:
                files = {
                    'file': ('audio.mp3', audio_file, 'audio/mpeg'),
                    'model': (None, 'whisper-1'),
                }
                
                # Make the API request to OpenAI
                response = requests.post(
                    'https://api.openai.com/v1/audio/transcriptions',
                    headers=headers,
                    files=files
                )
            
            if response.status_code == 200:
                result = response.json()
                return Response({'transcription': result.get('text', '')})
            else:
                return Response({'error': f'Transcription failed: {response.text}'}, status=response.status_code)
            
        finally:
            # Clean up temporary file
            try:
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)
            except Exception as e:
                print(f"Error deleting temporary file: {e}")
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auto_reply(request):
    try:
        messages = request.data.get('messages', [])
        chat_id = request.data.get('chat_id')
        recipient_id = request.data.get('recipient')
        
        if not messages or not chat_id or not recipient_id:
            return Response({'error': 'Missing required data'}, status=400)
        
        # Get the chat
        try:
            chat = Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            return Response({'error': 'Chat not found'}, status=404)
        
        # Prepare conversation context for GPT
        conversation_context = ""
        for msg in messages:
            sender_name = "You" if msg['sender'] == request.user.id else "Other person"
            message_type = msg.get('type', 'text')
            
            if message_type == 'audio_transcribed':
                conversation_context += f"{sender_name}: {msg['text']}\n"
            else:
                conversation_context += f"{sender_name}: {msg['text']}\n"
        
        # Create GPT prompt
        prompt = f"""Based on the following conversation, generate a very short and casual reply like in a messenger chat. 
        Keep it brief, friendly, and conversational - similar to how people reply in WhatsApp or Facebook Messenger.
        Maximum 2-3 sentences or even shorter if appropriate.
        
        Note: Some messages were transcribed from voice messages and are marked as "(voice message)".
        
        Conversation:
        {conversation_context}
        
        Your short reply:"""
        
        # Call GPT API (using OpenAI ChatGPT as configured in settings)
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates very short, casual replies for messenger chats. Keep replies brief, friendly, and conversational - like quick text messages. Never write more than 2-3 short sentences."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 50,
            "temperature": 0.8
        }
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            auto_reply_text = result['choices'][0]['message']['content'].strip()
            
            # Return the generated reply text to be filled in the input box
            return Response({
                'success': True, 
                'message': 'Auto reply generated successfully',
                'reply_text': auto_reply_text,
                'prompt': prompt,
            })
        else:
            return Response({'error': f'GPT API error: {response.text}'}, status=response.status_code)
            
    except Exception as e:
        return Response({'error': str(e)}, status=500)



