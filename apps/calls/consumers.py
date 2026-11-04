import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings


class CommandConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # احراز هویت ساده با API Key از query string: ?key=xxx
        query = self.scope.get('query_string', b'').decode()
        params = dict(x.split('=') for x in query.split('&') if '=' in x)
        key = params.get('key', '')

        if key != getattr(settings, 'PHONE_SYNC_API_KEY', ''):
            await self.close()
            return

        self.group_name = 'phone_commands'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({'type': 'connected', 'message': 'OK'}))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # فعلاً نیازی به دریافت از گوشی نیست
        pass

    async def new_command(self, event):
        """وقتی از داشبورد دستور جدید ثبت شد، این متد صدا زده می‌شود"""
        await self.send(text_data=json.dumps({
            'type': 'command',
            'id': event['id'],
            'command_type': event['command_type'],
            'number': event['number'],
            'body': event.get('body') or '',
        }))