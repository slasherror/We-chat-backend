from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from chat.models import KeyPair
from chat.utils import generate_key_pair

# @receiver(post_save, sender=User)
# def create_key_pair(sender, instance, created, **kwargs):
#     if created:
#         private_key, public_key = generate_key_pair()
#         KeyPair.objects.create(user=instance, private_key=private_key, public_key=public_key)