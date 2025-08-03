from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        # Add custom user data to the response
        user = self.user
        data.update({
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
         
            }
        })

        return data
