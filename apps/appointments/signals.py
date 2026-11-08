from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from apps.appointments.models.appointment import Appointment, AppointmentLog
from django.utils.encoding import force_str


TRACKED_FIELDS = [
    'patient',
    'first_name',
    'last_name',
    'phone_number_1',
    'phone_number_2',
    'referrer',
    'date',
    'start_time',
    'end_time',
    'appointment_type',
    'status',
    'status_note',
    'extra_data',
]


def serialize_value(value):
    if value is None:
        return None

    if hasattr(value, 'isoformat'):
        return value.isoformat()

    if isinstance(value, dict):
        return value

    return str(value)


def get_choice_label(model_instance, field_name, value):
    if value is None:
        return None

    field = model_instance._meta.get_field(field_name)
    if field.choices:
        return force_str(dict(field.choices).get(value, value))

    return value


def build_change_data(instance, field_name, old_value, new_value):
    old_serialized = old_value.pk if field_name == 'patient' and old_value else old_value
    new_serialized = new_value.pk if field_name == 'patient' and new_value else new_value

    data = {
        'old': serialize_value(old_serialized),
        'new': serialize_value(new_serialized),
    }

    field = instance._meta.get_field(field_name)
    if field.choices:
        data['old_label'] = get_choice_label(instance, field_name, old_serialized)
        data['new_label'] = get_choice_label(instance, field_name, new_serialized)

    return data


@receiver(pre_save, sender=Appointment)
def appointment_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_instance = None
        return

    try:
        instance._old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        instance._old_instance = None


@receiver(post_save, sender=Appointment)
def appointment_post_save(sender, instance, created, **kwargs):
    changed_by = getattr(instance, '_changed_by', None)

    if created:
        initial_data = {}
        for field in TRACKED_FIELDS:
            value = getattr(instance, field, None)
            if field == 'patient':
                value = value.pk if value else None
            initial_data[field] = serialize_value(value)

        AppointmentLog.objects.create(
            appointment=instance,
            appointment_snapshot_id=instance.pk,
            action='create',
            changed_by=changed_by,
            description='نوبت جدید ثبت شد',
            changes=initial_data,
        )
        return

    old_instance = getattr(instance, '_old_instance', None)
    if not old_instance:
        return

    changes = {}

    for field_name in TRACKED_FIELDS:
        old_value = getattr(old_instance, field_name, None)
        new_value = getattr(instance, field_name, None)

        old_compare = old_value.pk if field_name == 'patient' and old_value else old_value
        new_compare = new_value.pk if field_name == 'patient' and new_value else new_value

        if old_compare != new_compare:
            changes[field_name] = build_change_data(instance, field_name, old_value, new_value)

    if not changes:
        return

    only_status_changed = set(changes.keys()) <= {'status', 'status_note'}

    AppointmentLog.objects.create(
        appointment=instance,
        appointment_snapshot_id=instance.pk,
        action='status_change' if only_status_changed else 'update',
        changed_by=changed_by,
        field_name='status' if only_status_changed else None,
        old_value=changes.get('status', {}).get('old') if 'status' in changes else None,
        new_value=changes.get('status', {}).get('new') if 'status' in changes else None,
        changes=changes,
        description='وضعیت نوبت تغییر کرد' if only_status_changed else 'اطلاعات نوبت ویرایش شد',
    )


@receiver(post_delete, sender=Appointment)
def appointment_post_delete(sender, instance, **kwargs):
    changed_by = getattr(instance, '_changed_by', None)

    deleted_data = {}
    for field in TRACKED_FIELDS:
        value = getattr(instance, field, None)
        if field == 'patient':
            value = value.pk if value else None
        deleted_data[field] = serialize_value(value)

    AppointmentLog.objects.create(
        appointment=None,                          # درست
        appointment_snapshot_id=instance.pk,       # درست
        action='delete',
        changed_by=changed_by,
        description='نوبت حذف شد',
        changes=deleted_data,
    )