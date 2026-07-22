/**
 * persian-date replacement
 * Only implements: new persianDate() → امروز شمسی
 */
(function (global) {
  function persianDate(input) {
    const FA = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];
    function toJalali(gy, gm, gd) {
      const g_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
      const j_days = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];
      gy -= 1600;
      gm -= 1;
      gd -= 1;
      let g_d_no =
        365 * gy +
        Math.floor((gy + 3) / 4) -
        Math.floor((gy + 99) / 100) +
        Math.floor((gy + 399) / 400);
      for (let i = 0; i < gm; ++i) g_d_no += g_days[i];
      if (gm > 1 && ((gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0))
        ++g_d_no;
      g_d_no += gd;
      let j_d_no = g_d_no - 79;
      let j_np = Math.floor(j_d_no / 12053);
      j_d_no %= 12053;
      let jy = 979 + 33 * j_np + 4 * Math.floor(j_d_no / 1461);
      j_d_no %= 1461;
      if (j_d_no >= 366) {
        jy += Math.floor((j_d_no - 1) / 365);
        j_d_no = (j_d_no - 1) % 365;
      }
      let i = 0;
      const jm_days = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];
      for (; i < 11 && j_d_no >= jm_days[i]; ++i) j_d_no -= jm_days[i];
      return [jy, i + 1, j_d_no + 1];
    }
    const now = new Date();
    const j = toJalali(now.getFullYear(), now.getMonth() + 1, now.getDate());
    this._y = j[0];
    this._m = j[1];
    this._d = j[2];

    this.year = function () {
      return this._y;
    };
    this.month = function () {
      return this._m;
    };
    this.date = function () {
      return this._d;
    };
  }
  global.persianDate = persianDate;
})(window);
