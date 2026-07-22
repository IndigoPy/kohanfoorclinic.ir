document.addEventListener('DOMContentLoaded', function () {
  document.addEventListener('click', function (e) {
    const printBtn = e.target.closest('.print-invoice-btn');
    if (!printBtn) return;

    const targetId = printBtn.dataset.printTarget;
    const target = document.getElementById(targetId);
    if (!target) return;

    const printWindow = window.open('', '_blank', 'width=900,height=700');
    if (!printWindow) return;

    printWindow.document.write(`
      <html lang="fa" dir="rtl">
        <head>
          <meta charset="UTF-8">
          <title>چاپ فاکتور</title>
          <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.rtl.min.css">
          <style>
            body {
              font-family: Tahoma, Arial, sans-serif;
              padding: 24px;
              background: #fff;
              color: #111;
            }
            .invoice-sheet {
              direction: rtl;
            }
            .table th, .table td {
              font-size: 13px;
              vertical-align: middle;
            }
            @media print {
              body {
                padding: 0;
              }
            }
          </style>
        </head>
        <body>
          ${target.innerHTML}
        </body>
      </html>
    `);

    printWindow.document.close();
    printWindow.focus();

    setTimeout(function () {
      printWindow.print();
    }, 300);
  });
});
