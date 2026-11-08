(function ($) {
    const CATEGORIES = [
        ['doctor', 'پزشک'], ['physiotherapist', 'فیزیوتراپ'],
        ['orthopedist', 'ارتوپد'], ['shoe_store', 'فروشگاه کفش'], ['other', 'سایر']
    ];

    function getCookie(name) {
        const m = document.cookie.match('(^|;)\\s*' + name + '=([^;]+)');
        return m ? decodeURIComponent(m[2]) : '';
    }

    function buildQuickAdd($sel) {
        const quickUrl = $sel.data('quick-url');
        if (!quickUrl) return;

        const $wrap = $sel.parent();
        $wrap.find('.referrer-quick').remove();

        const $toggle = $('<button type="button" class="btn btn-link btn-sm p-0 mt-1"></button>')
            .html('<i class="fa-solid fa-user-plus me-1"></i>ثبت معرف جدید');

        const $panel = $('<div class="border rounded-3 p-3 mt-2 bg-light d-none"></div>');
        const $name = $('<input type="text" class="form-control form-control-sm mb-2" placeholder="نام و نام خانوادگی *">');
        const $cat = $('<select class="form-select form-select-sm mb-2"></select>');
        CATEGORIES.forEach(c => $cat.append($('<option></option>').val(c[0]).text(c[1])));
        const $workplace = $('<input type="text" class="form-control form-control-sm mb-2" placeholder="محل کار (اختیاری)">');
        const $phone = $('<input type="text" dir="ltr" class="form-control form-control-sm mb-2" placeholder="تلفن (اختیاری)">');
        const $save = $('<button type="button" class="btn btn-success btn-sm">ذخیره و انتخاب</button>');
        const $cancel = $('<button type="button" class="btn btn-light btn-sm border ms-1">انصراف</button>');
        $panel.append($name, $cat, $workplace, $phone, $save, $cancel);

        const $box = $('<div class="referrer-quick"></div>').append($toggle, $panel);
        $wrap.append($box);

        $toggle.on('click', () => { $panel.toggleClass('d-none'); $name.trigger('focus'); });
        $cancel.on('click', () => $panel.addClass('d-none'));

        $save.on('click', function () {
            if (!$name.val().trim()) { $name.addClass('is-invalid'); return; }
            $name.removeClass('is-invalid');
            $save.prop('disabled', true);

            $.ajax({
                url: quickUrl, method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
                data: {
                    full_name: $name.val(), category: $cat.val(),
                    workplace: $workplace.val(), phone: $phone.val()
                }
            }).done(function (res) {
                $sel.append(new Option(res.text, res.id, true, true)).trigger('change');
                $name.val(''); $workplace.val(''); $phone.val('');
                $panel.addClass('d-none');
            }).fail(function (xhr) {
                alert((xhr.responseJSON && xhr.responseJSON.error) || 'خطا در ثبت معرف.');
            }).always(() => $save.prop('disabled', false));
        });
    }

    window.initReferrerSelects = function (ctx) {
        $(ctx).find('select.referrer-select').each(function () {
            const $sel = $(this);
            if ($sel.data('select2')) $sel.select2('destroy');

            const $modal = $sel.closest('.modal');
            $sel.select2({
                width: '100%',
                dir: 'rtl',
                allowClear: true,
                placeholder: $sel.data('placeholder') || 'جستجوی معرف یا بیمار...',
                minimumInputLength: 1,
                dropdownParent: $modal.length ? $modal : $(document.body),
                tags: true,
                createTag: function (params) {
                    const term = $.trim(params.term);
                    if (!term) return null;
                    return { id: 'txt:' + term, text: term, meta: 'متن آزاد (بدون ثبت در لیست معرفین)', newTag: true };
                },
                ajax: {
                    url: $sel.data('url'),
                    dataType: 'json',
                    delay: 250,
                    data: p => ({ q: p.term, exclude: $sel.data('exclude') || '' }),
                    processResults: d => ({ results: d.results || [] })
                },
                templateResult: function (item) {
                    if (item.loading || !item.id) return item.text;
                    const $row = $('<div></div>');
                    $('<div class="fw-semibold"></div>').text(item.text).appendTo($row);
                    if (item.meta) $('<small class="text-muted"></small>').text(item.meta).appendTo($row);
                    return $row;
                },
                language: {
                    inputTooShort: () => 'نام، شناسه، شماره پرونده یا تلفن را تایپ کنید',
                    searching: () => 'در حال جستجو...',
                    noResults: () => 'موردی یافت نشد؛ می‌توانید متن آزاد یا معرف جدید ثبت کنید'
                }
            });

            buildQuickAdd($sel);
        });
    };
})(jQuery);