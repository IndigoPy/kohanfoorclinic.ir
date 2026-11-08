from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import PendingCommand


def queue_sms_commands(numbers, body, device_id='main-phone'):
    """برای هر شماره یک دستور پیامک در صف می‌سازد و لیست دستورات را برمی‌گرداند."""
    commands = []
    seen = set()

    for raw in numbers:
        number = (raw or '').strip()
        if not number or number in seen:
            continue
        seen.add(number)

        commands.append(PendingCommand.objects.create(
            command_type=PendingCommand.COMMAND_SMS,
            number=number,
            body=body,
            status=PendingCommand.STATUS_PENDING,
            device_id=device_id,
        ))

    _notify_phone(commands)
    return commands


def _notify_phone(commands):
    """اطلاع‌رسانی لحظه‌ای از طریق WebSocket؛ در صورت خطا نادیده گرفته می‌شود
    چون اپ گوشی با polling هم دستور را می‌گیرد."""
    layer = get_channel_layer()
    if layer is None:
        return

    for cmd in commands:
        try:
            async_to_sync(layer.group_send)('phone_commands', {
                'type': 'new_command',
                'id': cmd.id,
                'command_type': cmd.command_type,
                'number': cmd.number,
                'body': cmd.body or '',
            })
        except Exception:
            pass