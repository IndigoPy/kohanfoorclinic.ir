from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.reception.models.orders import extract_foot_length
from apps.reception.utils import normalize_digits
from apps.workshop.models import WorkshopStatusLog
from apps.workshop.services.logging import create_workshop_log

TRUE_VALUES = (True, 'true', 'True', 'on', '1', 1)
SIDE_LABELS = {'right': ' (راست)', 'left': ' (چپ)'}


def _options(field):
    return [o.strip() for o in (field.dropdown_options or '').split(',') if o.strip()]


def _read(post, key, field):
    if field.field_type == 'checkbox':
        return post.get(key) == 'true'
    value = (post.get(key) or '').strip()
    if field.field_type == 'number':
        value = normalize_digits(value).replace('٫', '.')
    return value


def _validate(fields, values, where, check_required):
    errors = []
    for f in fields:
        v = values.get(f.name)
        if f.field_type == 'checkbox':
            continue
        if v in ('', None):
            if check_required and f.is_required:
                errors.append(f'«{f.label}»{where} اجباری است.')
            continue
        if f.field_type == 'number':
            try:
                Decimal(v)
            except InvalidOperation:
                errors.append(f'«{f.label}»{where} باید عدد باشد.')
        elif f.field_type == 'select' and v not in _options(f):
            errors.append(f'مقدار «{f.label}»{where} معتبر نیست.')
    return errors


def _flatten(data, prefix=''):
    out = {}
    for key, value in (data or {}).items():
        if key == 'different_sizes':
            continue
        if isinstance(value, dict):
            out.update(_flatten(value, f'{key}.'))
        else:
            out[f'{prefix}{key}'] = value
    return out


def _norm(value):
    return '' if value is None else str(value)


def _changed_labels(old_m, new_m, old_d, new_d, labels):
    changed = []
    if bool((old_m or {}).get('different_sizes')) != bool(new_m.get('different_sizes')):
        changed.append('نوع اندازه (یکسان/چپ و راست)')
    for old, new in ((_flatten(old_m), _flatten(new_m)), (old_d or {}, new_d)):
        for key in set(old) | set(new):
            if _norm(old.get(key)) != _norm(new.get(key)):
                side, _, name = key.rpartition('.')
                name = name or side if not side else name
                base = key.split('.')[-1]
                suffix = SIDE_LABELS.get(key.split('.')[0], '') if '.' in key else ''
                changed.append(labels.get(base, base) + suffix)
    return changed


def save_item_specs(*, item, post, user, complete):
    meas_fields = list(item.service.measurements.all())
    dyn_fields = list(item.service.dynamic_fields.all())
    labels = {f.name: f.label for f in meas_fields + dyn_fields}

    different = post.get('size_mode') == 'different'

    def read_meas(prefix):
        return {f.name: _read(post, f'{prefix}{f.name}', f) for f in meas_fields}

    if different:
        measurements = {'different_sizes': True,
                        'right': read_meas('meas_right_'),
                        'left': read_meas('meas_left_')}
    else:
        measurements = {'different_sizes': False, **read_meas('meas_')}
    dynamic = {f.name: _read(post, f'dyn_{f.name}', f) for f in dyn_fields}

    errors = []
    if different:
        for side, where in (('right', ' (پای راست)'), ('left', ' (پای چپ)')):
            errors += _validate(meas_fields, measurements[side], where, complete)
    else:
        errors += _validate(meas_fields, measurements, '', complete)
    errors += _validate(dyn_fields, dynamic, '', complete)
    if errors:
        raise ValueError(' | '.join(errors))

    changed = _changed_labels(item.measurements, measurements, item.dynamic_fields, dynamic, labels)
    newly_completed = complete and item.specs_status != 'completed'
    if not changed and not newly_completed:
        return []

    item.measurements = measurements
    item.dynamic_fields = dynamic
    item.foot_length = extract_foot_length(measurements)
    update_fields = ['measurements', 'dynamic_fields', 'foot_length', 'updated_at']

    if newly_completed:
        item.specs_status = 'completed'
        item.specs_completed_by = user
        item.specs_completed_at = timezone.now()
        update_fields += ['specs_status', 'specs_completed_by', 'specs_completed_at']
    item.save(update_fields=update_fields)

    parts = []
    if newly_completed:
        parts.append('مشخصات تکمیل و تایید شد.')
    if changed:
        parts.append('تغییر در: ' + '، '.join(sorted(set(changed))))
    create_workshop_log(
        order=item.order, item=item, created_by=user,
        action=WorkshopStatusLog.ACTION_SPECS_UPDATE,
        description=' '.join(parts),
    )
    return changed


def get_spec_context(item):
    """داده آماده‌ی رندر فرم مشخصات در تمپلیت."""
    service = item.service
    meas_fields = list(service.measurements.all())
    dyn_fields = list(service.dynamic_fields.all())

    m = item.measurements or {}
    different = bool(m.get('different_sizes'))
    right = (m.get('right') or {}) if different else m
    left = (m.get('left') or {}) if different else m
    dyn = item.dynamic_fields or {}

    def rows(fields, values):
        out = []
        for f in fields:
            value = values.get(f.name, '')
            if f.field_type == 'checkbox':
                value = value in TRUE_VALUES
            out.append({
                'name': f.name, 'label': f.label, 'type': f.field_type,
                'required': f.is_required, 'options': _options(f), 'value': value,
            })
        return out

    return {
        'different': different,
        'has_schema': bool(meas_fields or dyn_fields),
        'same_fields': rows(meas_fields, right),
        'right_fields': rows(meas_fields, right),
        'left_fields': rows(meas_fields, left),
        'dynamic_fields': rows(dyn_fields, dyn),
    }