import pandas as pd
import math
import jdatetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from ...models.patient import Patient  

class Command(BaseCommand):
    help = 'Import patients from an Excel file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the excel file')

    def clean_value(self, val):
        """تبدیل مقادیر نامعتبر به None"""
        if pd.isna(val) or str(val).strip() in ['-', 'ندارد', '']:
            return None
        return str(val).strip()

    def parse_date(self, date_str):
        """تبدیل تاریخ شمسی/میلادی به آبجکت date میلادی"""
        if not date_str:
            return None
        date_str = str(date_str).replace('/', '-')
        try:
            # بررسی اینکه آیا تاریخ میلادی است (مثلا با 20 شروع می‌شود)
            if date_str.startswith('20'):
                return pd.to_datetime(date_str).date()
            else:
                # فرض بر تاریخ شمسی
                parts = date_str.split('-')
                if len(parts) == 3:
                    j_date = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                    return j_date.togregorian()
        except:
            return None
        return None

    def calculate_birth_date(self, age_str):
        """محاسبه تقریبی تاریخ تولد بر اساس سن"""
        age = self.clean_value(age_str)
        if not age or not age.isdigit():
            return None
        current_j_year = jdatetime.date.today().year
        birth_j_year = current_j_year - int(age)
        # فرض میکنیم روز و ماه ۱ فروردین است
        return jdatetime.date(birth_j_year, 1, 1).togregorian()

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        df = pd.read_excel(file_path, sheet_name='Main', dtype=str)

        # دیکشنری برای نگهداری روابط الصاق به منظور آپدیت در مرحله دوم
        attached_relations = {}

        self.stdout.write("Starting import...")

        for index, row in df.iterrows():
            # نام و نام خانوادگی در نمونه شما در دو ستون جداگانه دیده می‌شوند 
            # فرض می‌کنیم ستون 1 نام و ستون 2 نام خانوادگی است بر اساس دیتای نمونه
            case_number = self.clean_value(row.iloc[0])
            if not case_number:
                continue

            first_name = self.clean_value(row.iloc[1]) or "نامشخص"
            last_name = self.clean_value(row.iloc[2]) or "نامشخص"
            
            admission_date_raw = self.clean_value(row.iloc[3])
            admission_date = self.parse_date(admission_date_raw) or timezone.now().date()

            phone = self.clean_value(row.iloc[5])  or "00000000000"
            alt_phone = self.clean_value(row.iloc[6]) if self.clean_value(row.iloc[6]) else None

            # پردازش جنسیت
            gender_raw = self.clean_value(row.iloc[17])
            gender = 'male' if gender_raw == 'مرد' else 'female'

            # پردازش سایز پا (تبدیل به int)
            foot_size_raw = self.clean_value(row.iloc[11])
            foot_size = int(foot_size_raw) if foot_size_raw and foot_size_raw.isdigit() else None

            # ایجاد یا آپدیت بیمار
            patient, created = Patient.objects.update_or_create(
                case_number=case_number,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'birth_date': self.calculate_birth_date(row.iloc[7]),
                    'national_id': self.clean_value(row.iloc[8]),
                    'weight': self.clean_value(row.iloc[9]),
                    'height': self.clean_value(row.iloc[10]),
                    'gender': gender,
                    'phone': phone,
                    'alternative_phone': alt_phone,
                    'referrer': self.clean_value(row.iloc[12]),
                    'visit_reason': self.clean_value(row.iloc[13]),
                    'orthotic_history': self.clean_value(row.iloc[14]),
                    'underlying_diseases': self.clean_value(row.iloc[15]),
                    'reception_notes': self.clean_value(row.iloc[16]),
                    'admission_date': admission_date,
                    'foot_size': foot_size,
                }
            )

            # ذخیره رابطه الصاق برای مرحله بعد
            attached_to_raw = self.clean_value(row.iloc[18])
            if attached_to_raw:
                attached_relations[patient.id] = attached_to_raw

        # مرحله دوم: تنظیم روابط الصاق (Foreign Key به خود جدول)
        self.stdout.write("Setting up attachments...")
        for patient_id, target_case_number in attached_relations.items():
            target_patient = Patient.objects.filter(case_number=target_case_number).first()
            if target_patient:
                Patient.objects.filter(id=patient_id).update(attached_to=target_patient)

        self.stdout.write(self.style.SUCCESS("Import completed successfully!"))
