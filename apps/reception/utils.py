def standardize_persian_date(date_str):
    if not date_str:
        return None
    # جدول تبدیل اعداد فارسی به انگلیسی
    persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    # تبدیل اعداد
    english_digits_date = date_str.translate(persian_to_english)
    # جایگزینی اسلش با خط تیره
    return english_digits_date.replace('/', '-')