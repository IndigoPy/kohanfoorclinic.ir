import jdatetime
from django.utils import timezone

def standardize_persian_date(date_str):
    if not date_str:
        return None
    # جدول تبدیل اعداد فارسی به انگلیسی
    persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    # تبدیل اعداد
    english_digits_date = date_str.translate(persian_to_english)
    # جایگزینی اسلش با خط تیره
    return english_digits_date.replace('/', '-')

def normalize_digits(value):
    return str(value or '').translate(
        str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
    )


def resolve_referrer(raw):
    """ref:12 | pat:34 | txt:متن | متن قدیمی  ->  (نام نمایشی, بیمار, معرف)"""
    from .models import Patient, Referrer

    raw = (raw or '').strip()
    prefix, _, rest = raw.partition(':')

    if prefix in ('ref', 'pat') and rest.isdigit():
        if prefix == 'ref':
            person = Referrer.objects.filter(pk=int(rest)).first()
            if person:
                return person.full_name, None, person
        else:
            patient = Patient.objects.filter(pk=int(rest)).first()
            if patient:
                return patient.full_name, patient, None
        return '', None, None

    if prefix == 'txt':
        return rest.strip()[:255], None, None

    return raw[:255], None, None


def _referrer_choice(text, patient, person):
    if person:
        return {'id': f'ref:{person.pk}', 'text': f'{person.full_name} ({person.code})'}
    if patient:
        return {'id': f'pat:{patient.pk}', 'text': f'{patient.full_name} ({patient.case_number})'}
    text = (text or '').strip()
    if text:
        return {'id': f'txt:{text}', 'text': text}
    return None


def referrer_initial(obj):
    """برای Patient یا Appointment: گزینهٔ انتخاب‌شدهٔ فعلی"""
    if obj is None:
        return None
    return _referrer_choice(obj.referrer, obj.referrer_patient, obj.referrer_person)


def referrer_initial_from_raw(raw):
    return _referrer_choice(*resolve_referrer(raw))

def parse_jalali_datetime(raw):
    """'۱۴۰۵/۰۴/۳۰' → datetime آگاه به منطقهٔ زمانی (ساعت = اکنون)."""
    try:
        y, m, d = map(int, normalize_digits(raw).strip().replace('-', '/').split('/'))
        now = timezone.localtime()
        g = jdatetime.datetime(y, m, d, now.hour, now.minute, now.second).togregorian()
        return timezone.make_aware(g) if timezone.is_naive(g) else g
    except (ValueError, TypeError):
        return None

def to_persian_date_str(value):
    """date یا datetime میلادی → '1405/04/30' (برای نمایش در input)."""
    if not value:
        return ''
    if hasattr(value, 'astimezone') and timezone.is_aware(value):
        value = timezone.localtime(value)
    j = jdatetime.date.fromgregorian(date=value.date() if hasattr(value, 'date') else value)
    return f"{j.year}/{j.month:02d}/{j.day:02d}"