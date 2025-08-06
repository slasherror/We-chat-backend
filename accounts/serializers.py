# accounts/serializers.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        user = self.user
        request = self.context.get("request")

        # Add custom user data to the token response
        data.update({
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            }
        })

        # Send login alert email
        if user and request:
            ip_address = request.META.get('REMOTE_ADDR', '')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            login_time = timezone.now()
            
            subject = "Login Alert"
            message = (
                f"Hello {user.username},\n\n"
                f"You logged in on {login_time}.\n"
                f"IP Address: {ip_address}\n"
                f"User-Agent: {user_agent}\n\n"
                "If this was not you, please contact support."
            )
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]
            
            send_mail(subject, message, from_email, recipient_list, fail_silently=False)

        return data
