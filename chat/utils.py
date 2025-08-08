from Crypto.PublicKey import RSA

import base64

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
from base64 import b64encode, b64decode
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives import hashes
import os
from Crypto.Util.Padding import unpad, pad


def generate_key_pair():
    key = RSA.generate(2048)
    private_key = key.export_key().decode('utf-8')
    public_key = key.publickey().export_key().decode('utf-8')
    return private_key, public_key

def encrypt_message(public_key_str, message):
    public_key = RSA.import_key(public_key_str)
    cipher = PKCS1_OAEP.new(public_key)
    chunk_size = 190  # Max size depends on the key size and padding
    chunks = [message[i:i + chunk_size] for i in range(0, len(message), chunk_size)]
    
    encrypted_chunks = [b64encode(cipher.encrypt(chunk.encode())) for chunk in chunks]
    return '||'.join([chunk.decode('utf-8') for chunk in encrypted_chunks])



def decrypt_message(private_key_str, encrypted_message):
    private_key = RSA.import_key(private_key_str)
    cipher = PKCS1_OAEP.new(private_key)
    
    # Split the encrypted message into chunks
    encrypted_chunks = encrypted_message.split('||')
    decrypted_chunks = [cipher.decrypt(b64decode(chunk.encode())).decode('utf-8') for chunk in encrypted_chunks]
    return ''.join(decrypted_chunks)


def encrypt_final_audio(audio, public_key_pem):
    
    audio_data = audio

    public_key = RSA.import_key(public_key_pem)
    aes_key = os.urandom(32)  # Generate a random AES key (256 bits)
    iv = b"ANIK@&01NAFIUL#$"  # Static IV
    
    cipher_aes = AES.new(aes_key, AES.MODE_CBC, iv)
    encrypted_audio = cipher_aes.encrypt(audio_data.ljust(len(audio_data) + AES.block_size - len(audio_data) % AES.block_size, b'\0'))  # Padding

    cipher_rsa = PKCS1_OAEP.new(public_key)
    encrypted_aes_key = cipher_rsa.encrypt(aes_key)

    return encrypted_audio, encrypted_aes_key, iv




def decrypt_final_audio(encrypted_audio,encrypted_aes_key,iv,private_key_pem):

    private_key = RSA.import_key(private_key_pem)  # Import the key as an RSA object

    cipher_rsa = PKCS1_OAEP.new(private_key)
    aes_key = cipher_rsa.decrypt(encrypted_aes_key)

    # Use static IV
    cipher_aes = AES.new(aes_key, AES.MODE_CBC, b"ANIK@&01NAFIUL#$")
    decrypted_audio = cipher_aes.decrypt(encrypted_audio)

    decrypted_audio = decrypted_audio.rstrip(b'\0')  # Remove padding
    base64_audio = base64.b64encode(decrypted_audio).decode('utf-8')

    return base64_audio
