/**
 * Jalali Datepicker - Pure JS/jQuery
 * No external dependencies
 * Compatible with persian-datepicker API ($.fn.persianDatepicker)
 */

(function ($) {
  "use strict";

  // ─── Jalali Algorithm ────────────────────────────────────────────────────

  const Jalali = {
    // تبدیل تاریخ میلادی به شمسی
    toJalali: function (gy, gm, gd) {
      let g_d_no, j_d_no, j_np, i;
      const g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
      const j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];

      gy -= 1600;
      gm -= 1;
      gd -= 1;
      g_d_no =
        365 * gy +
        Math.floor((gy + 3) / 4) -
        Math.floor((gy + 99) / 100) +
        Math.floor((gy + 399) / 400);
      for (i = 0; i < gm; ++i) g_d_no += g_days_in_month[i];
      if (gm > 1 && ((gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0))
        ++g_d_no;
      g_d_no += gd;

      j_d_no = g_d_no - 79;
      j_np = Math.floor(j_d_no / 12053);
      j_d_no %= 12053;
      let jy = 979 + 33 * j_np + 4 * Math.floor(j_d_no / 1461);
      j_d_no %= 1461;
      if (j_d_no >= 366) {
        jy += Math.floor((j_d_no - 1) / 365);
        j_d_no = (j_d_no - 1) % 365;
      }
      for (i = 0; i < 11 && j_d_no >= j_days_in_month[i]; ++i)
        j_d_no -= j_days_in_month[i];
      return [jy, i + 1, j_d_no + 1];
    },

    // تبدیل تاریخ شمسی به میلادی
    toGregorian: function (jy, jm, jd) {
      jy += 1595;
      jm -= 1;
      let days =
        -355779 +
        365 * jy +
        Math.floor(jy / 33) * 8 +
        Math.floor(((jy % 33) + 3) / 4) +
        jm * 30 +
        Math.min(jm, 6) +
        jd;
      let gy = 400 * Math.floor(days / 146097);
      days %= 146097;
      if (days > 36524) {
        gy += 100 * Math.floor(--days / 36524);
        days %= 36524;
        if (days >= 365) days++;
      }
      gy += 4 * Math.floor(days / 1461);
      days %= 1461;
      if (days > 365) {
        gy += Math.floor((days - 1) / 365);
        days = (days - 1) % 365;
      }
      const gd_no = days + 1;
      const sal_a = [
        0,
        31,
        (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0 ? 29 : 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
      ];
      let gm = 0;
      let rem = gd_no;
      for (let i = 1; i <= 12; i++) {
        if (rem <= sal_a[i]) {
          gm = i;
          break;
        }
        rem -= sal_a[i];
      }
      return [gy, gm, rem];
    },

    // تعداد روزهای ماه شمسی
    daysInMonth: function (jy, jm) {
      if (jm <= 6) return 31;
      if (jm <= 11) return 30;
      return this.isLeap(jy) ? 30 : 29;
    },

    // سال کبیسه (محاسبه نجومی)
    isLeap: function (jy) {
      const breaks = [
        -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097,
        2192, 2262, 2324, 2394, 2456, 3178,
      ];
      let bl = breaks.length,
        jp = breaks[0],
        jm,
        jump;
      if (jy < jp || jy >= breaks[bl - 1]) return false;
      for (let i = 1; i < bl; i++) {
        jm = breaks[i];
        jump = jm - jp;
        if (jy < jm) {
          let n = jy - jp;
          let leapJ = -14 + 33 * Math.floor((n + 14) / 33);
          let mod = n - leapJ;
          return (
            mod === 4 ||
            mod === 8 ||
            mod === 12 ||
            mod === 16 ||
            mod === 20 ||
            mod === 24 ||
            mod === 28 ||
            mod === 32
          );
        }
        jp = jm;
      }
      return false;
    },

    // گرفتن تاریخ امروز شمسی
    today: function () {
      const now = new Date();
      return this.toJalali(
        now.getFullYear(),
        now.getMonth() + 1,
        now.getDate(),
      );
    },
  };

  // ─── اعداد فارسی ─────────────────────────────────────────────────────────
  const FA_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];
  const MONTH_NAMES_FA = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
  ];
  const DAY_NAMES_FA = ["ش", "ی", "د", "س", "چ", "پ", "ج"];

  function toFaDigits(n) {
    return String(n)
      .split("")
      .map((c) => FA_DIGITS[+c] ?? c)
      .join("");
  }

  function padFa(n) {
    return toFaDigits(String(n).padStart(2, "0"));
  }

  // ─── Plugin ───────────────────────────────────────────────────────────────
  $.fn.persianDatepicker = function (optionsOrMethod) {
    // اگر متد string بود (مثل 'show')
    if (typeof optionsOrMethod === "string") {
      return this.each(function () {
        const inst = $(this).data("jalali-dp");
        if (inst && typeof inst[optionsOrMethod] === "function") {
          inst[optionsOrMethod]();
        }
      });
    }

    const defaults = {
      format: "YYYY/MM/DD",
      autoClose: true,
      initialValue: false,
      persianDigit: true,
      observer: true,
      onSelect: null,
    };
    const opts = $.extend(true, {}, defaults, optionsOrMethod);

    return this.each(function () {
      const $input = $(this);
      if ($input.data("jalali-dp")) return; // جلوگیری از تکرار

      // ── State ──
      let today = Jalali.today();
      let viewYear = today[0];
      let viewMonth = today[1];
      let selYear = null,
        selMonth = null,
        selDay = null;

      // ── ساخت DOM تقویم ──
      const $picker = $('<div class="jalali-picker" tabindex="-1"></div>');
      const $header = $('<div class="jalali-picker-header"></div>');
      const $prevBtn = $(
        '<button type="button" class="jalali-nav jalali-prev">&#8250;</button>',
      );
      const $nextBtn = $(
        '<button type="button" class="jalali-nav jalali-next">&#8249;</button>',
      );
      const $monthYear = $('<span class="jalali-month-year"></span>');
      const $grid = $('<div class="jalali-grid"></div>');
      const $yearGrid = $(
        '<div class="jalali-year-grid" style="display:none;"></div>',
      );
      const $footer = $('<div class="jalali-picker-footer"></div>');
      const $todayBtn = $(
        '<button type="button" class="jalali-today-btn">امروز</button>',
      );
      const $clearBtn = $(
        '<button type="button" class="jalali-clear-btn">پاک کردن</button>',
      );

      $header.append($nextBtn, $monthYear, $prevBtn);
      $footer.append($todayBtn, $clearBtn);
      $picker.append($header, $grid, $yearGrid, $footer);
      $picker.append($header, $grid, $footer);
      $("body").append($picker);

      // state برای نمای فعلی
      let viewMode = "days"; // "days" | "years"

      function renderYears() {
        $yearGrid.empty();
        const currentYear = Jalali.today()[0];
        const startYear = currentYear - 50;
        const endYear = currentYear + 10;

        for (let y = endYear; y >= startYear; y--) {
          const isCurrentYear = y === currentYear;
          const isSelectedYear = y === viewYear;

          const $cell = $('<div class="jalali-year-cell"></div>')
            .text(opts.persianDigit ? toFaDigits(y) : y)
            .data("year", y);

          if (isCurrentYear) $cell.addClass("jalali-today-year");
          if (isSelectedYear) $cell.addClass("jalali-selected-year");

          $yearGrid.append($cell);
        }

        // اسکرول به سال انتخاب‌شده یا امسال
        setTimeout(function () {
          const $target = $yearGrid
            .find(".jalali-selected-year, .jalali-today-year")
            .first();
          if ($target.length) {
            $yearGrid.scrollTop(
              $target.position().top +
                $yearGrid.scrollTop() -
                $yearGrid.height() / 2,
            );
          }
        }, 10);
      }

      // ── رندر تقویم ──
      function render() {
        $monthYear.html(
          MONTH_NAMES_FA[viewMonth - 1] +
            " " +
            toFaDigits(viewYear) +
            ' <small style="font-size:0.6em;opacity:0.7;">▼</small>',
        );
        $grid.empty();

        // سربرگ روزهای هفته (شنبه اول)
        DAY_NAMES_FA.forEach((d) => {
          $grid.append($('<div class="jalali-day-name"></div>').text(d));
        });

        const firstGreg = Jalali.toGregorian(viewYear, viewMonth, 1);
        const firstDate = new Date(
          firstGreg[0],
          firstGreg[1] - 1,
          firstGreg[2],
        );
        // 0=یکشنبه ... 6=شنبه  → ما شنبه=0 می‌خواهیم
        let startDow = (firstDate.getDay() + 1) % 7; // شنبه=0

        const totalDays = Jalali.daysInMonth(viewYear, viewMonth);

        // خانه‌های خالی اول
        for (let i = 0; i < startDow; i++) {
          $grid.append('<div class="jalali-cell jalali-empty"></div>');
        }

        for (let d = 1; d <= totalDays; d++) {
          const isToday =
            viewYear === today[0] && viewMonth === today[1] && d === today[2];
          const isSelected =
            selYear === viewYear && selMonth === viewMonth && selDay === d;
          const $cell = $('<div class="jalali-cell jalali-day"></div>')
            .text(opts.persianDigit ? toFaDigits(d) : d)
            .data("day", d);
          if (isToday) $cell.addClass("jalali-today");
          if (isSelected) $cell.addClass("jalali-selected");
          $grid.append($cell);
        }
      }

      // ── موقعیت‌دهی ──
      function position() {
        const off = $input.offset();
        const h = $input.outerHeight();
        const ww = $(window).width();
        const pw = $picker.outerWidth() || 280;
        let left = off.left;
        if (left + pw > ww - 10) left = ww - pw - 10;
        $picker.css({ top: off.top + h + 4, left: Math.max(5, left) });
      }

      // ── نمایش ──
      function show() {
        $(".jalali-picker").not($picker).hide(); // بستن بقیه
        render();
        position();
        $picker.show().focus();
      }

      // ── مخفی کردن ──
      function hide() {
        $picker.hide();
        $input.trigger("hide.persianDatepicker");
      }

      // ── فرمت کردن تاریخ ──
      function formatDate(y, m, d) {
        const yStr = opts.persianDigit ? toFaDigits(y) : String(y);
        const mStr = opts.persianDigit ? padFa(m) : String(m).padStart(2, "0");
        const dStr = opts.persianDigit ? padFa(d) : String(d).padStart(2, "0");
        return opts.format
          .replace("YYYY", yStr)
          .replace("MM", mStr)
          .replace("DD", dStr);
      }
      
      // --- کلیک روی عنوان: سوئیچ بین نمای روز و سال ---
      $monthYear.on("click", function (e) {
        e.stopPropagation();

        if (viewMode === "days") {
          // رفتن به نمای انتخاب سال
          viewMode = "years";
          $grid.hide();
          $prevBtn.hide();
          $nextBtn.hide();
          renderYears();
          $yearGrid.show();
          $monthYear.html(
            'انتخاب سال <small style="font-size:0.6em;opacity:0.7;">▲</small>',
          );
        } else {
          // برگشت به نمای روز
          viewMode = "days";
          $yearGrid.hide();
          $prevBtn.show();
          $nextBtn.show();
          $grid.show();
          render();
        }
      });

      // --- کلیک روی سال در نمای سال ---
      $yearGrid.on("click", ".jalali-year-cell", function (e) {
        e.stopPropagation();
        viewYear = $(this).data("year");
        viewMode = "days";

        $yearGrid.hide();
        $prevBtn.show();
        $nextBtn.show();
        $grid.show();
        render();
      });

      // ── پارس کردن مقدار input ──
      function parseInput(val) {
        if (!val) return null;
        // تبدیل ارقام فارسی به انگلیسی
        const ascii = val.replace(/[۰-۹]/g, (c) => FA_DIGITS.indexOf(c));
        const parts = ascii.split("/");
        if (parts.length !== 3) return null;
        const y = parseInt(parts[0]),
          m = parseInt(parts[1]),
          d = parseInt(parts[2]);
        if (isNaN(y) || isNaN(m) || isNaN(d)) return null;
        if (m < 1 || m > 12 || d < 1 || d > Jalali.daysInMonth(y, m))
          return null;
        return [y, m, d];
      }

      // ── انتخاب روز ──
      function selectDay(d) {
        selYear = viewYear;
        selMonth = viewMonth;
        selDay = d;
        const val = formatDate(selYear, selMonth, selDay);
        $input.val(val).trigger("change");
        render();
        if (opts.onSelect) {
          const greg = Jalali.toGregorian(selYear, selMonth, selDay);
          const unix = new Date(greg[0], greg[1] - 1, greg[2]).getTime();
          opts.onSelect(unix);
        }
        if (opts.autoClose) hide();
      }

      // ─── Event Listeners ──────────────────────────────────────────────

      // کلیک روز
      $grid.on("click", ".jalali-day", function () {
        selectDay($(this).data("day"));
      });

      // ماه بعد
      $nextBtn.on("click", function (e) {
        e.stopPropagation();
        viewMonth--;
        if (viewMonth < 1) {
          viewMonth = 12;
          viewYear--;
        }
        render();
      });

      // ماه قبل
      $prevBtn.on("click", function (e) {
        e.stopPropagation();
        viewMonth++;
        if (viewMonth > 12) {
          viewMonth = 1;
          viewYear++;
        }
        render();
      });

      // دکمه امروز
      $todayBtn.on("click", function (e) {
        e.stopPropagation();
        today = Jalali.today(); // بروزرسانی
        viewYear = today[0];
        viewMonth = today[1];
        selectDay(today[2]);
      });

      // دکمه پاک کردن
      $clearBtn.on("click", function (e) {
        e.stopPropagation();
        selYear = selMonth = selDay = null;
        $input.val("").trigger("change");
        render();
        hide();
      });

      // بستن با کلیک بیرون
      const uid = "jalali-" + Math.random().toString(36).slice(2, 9);
      $(document).on("click." + uid, function (e) {
        if (!$(e.target).closest($picker).length && !$(e.target).is($input)) {
          hide();
        }
      });

      // جلوگیری از بستن با کلیک داخل تقویم
      $picker.on("click", function (e) {
        e.stopPropagation();
      });

      // اگر observer فعال باشد، تغییر مستقیم input
      if (opts.observer) {
        $input.on("input.jalali", function () {
          const parsed = parseInput($(this).val());
          if (parsed) {
            selYear = parsed[0];
            selMonth = parsed[1];
            selDay = parsed[2];
            viewYear = selYear;
            viewMonth = selMonth;
            if ($picker.is(":visible")) render();
          }
        });
      }

      // ذخیره instance
      const inst = { show, hide, render };
      $input.data("jalali-dp", inst);

      // مقدار اولیه
      if (opts.initialValue !== false) {
        today = Jalali.today();
        selectDay(today[2]);
      }
    });
  };
})(jQuery);
