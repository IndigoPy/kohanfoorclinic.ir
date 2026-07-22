import os
import sys



# اجبار پایتون و محیط سرور به استفاده از UTF-8
os.environ['LANG'] = 'en_US.UTF-8'
os.environ['LC_ALL'] = 'en_US.UTF-8'
os.environ['PYTHONIOENCODING'] = 'UTF-8'
# مسیر اصلی پروژه خود را به path اضافه کنید
sys.path.insert(0, os.path.dirname(__file__))

# تنظیم متغیر محیطی تنظیمات جنگو (نام پوشه‌ای که settings.py در آن است را جایگزین kohanfootclinic کنید)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()