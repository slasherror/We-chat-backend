# middleware.py

import jwt
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.auth import AuthMiddleware
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.contrib.auth.models import User

class JWTAuthMiddleware(AuthMiddleware):
    """
    Custom WebSocket authentication middleware that extracts the JWT token from the URL
    query string and attaches the authenticated user to the scope.
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # Get token from query parameters
        query_params = parse_qs(scope.get("query_string", b"").decode())
        token = query_params.get("token", [None])[0]

        if token:
            try:
                # Decode the JWT token
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                # Attach the user to the scope
                user = await self.get_user(payload["user_id"])
                scope["user"] = user
            except jwt.ExpiredSignatureError:
                scope["user"] = AnonymousUser()
            except jwt.InvalidTokenError:
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)

    @database_sync_to_async
    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()
