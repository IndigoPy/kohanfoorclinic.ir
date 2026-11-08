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