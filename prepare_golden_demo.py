import sqlite3
from pathlib import Path

import seed_clean_demo


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
GUIDE_PATH = BASE_DIR / "GOLDEN_DEMO_GUIDE.md"


def scalar(cur, query, params=()):
    cur.execute(query, params)
    row = cur.fetchone()
    return row[0] if row else None


def write_guide():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    company_name = scalar(cur, "SELECT company_name FROM company_settings WHERE id=1") or "الشركة"
    subject_customer_id = scalar(cur, "SELECT id FROM customers WHERE withholding_status='subject' ORDER BY id LIMIT 1")
    normal_customer_id = scalar(cur, "SELECT id FROM customers WHERE withholding_status='non_subject' ORDER BY id LIMIT 1")
    taxable_supplier_id = scalar(cur, "SELECT id FROM suppliers WHERE withholding_status='taxable' ORDER BY id LIMIT 1")
    exempt_supplier_id = scalar(cur, "SELECT id FROM suppliers WHERE withholding_status='exempt' ORDER BY id LIMIT 1")
    sales_order_id = scalar(cur, "SELECT id FROM sales_orders ORDER BY id LIMIT 1")
    sales_delivery_id = scalar(cur, "SELECT id FROM sales_delivery_notes ORDER BY id LIMIT 1")
    sales_invoice_id = scalar(cur, "SELECT id FROM sales_invoices ORDER BY id LIMIT 1")
    financial_sales_invoice_id = scalar(cur, "SELECT id FROM financial_sales_invoices ORDER BY id LIMIT 1")
    purchase_order_id = scalar(cur, "SELECT id FROM purchase_orders ORDER BY id LIMIT 1")
    purchase_receipt_id = scalar(cur, "SELECT id FROM purchase_receipts ORDER BY id LIMIT 1")
    taxable_purchase_invoice_id = scalar(cur, "SELECT id FROM purchase_invoices WHERE withholding_amount > 0 ORDER BY id LIMIT 1")
    exempt_purchase_invoice_id = scalar(cur, "SELECT id FROM purchase_invoices WHERE COALESCE(withholding_amount,0)=0 ORDER BY id DESC LIMIT 1")
    receipt_id = scalar(cur, "SELECT id FROM receipt_vouchers ORDER BY id LIMIT 1")
    payment_id = scalar(cur, "SELECT id FROM payment_vouchers ORDER BY id LIMIT 1")
    trial_debit, trial_credit = cur.execute("SELECT ROUND(COALESCE(SUM(debit),0),2), ROUND(COALESCE(SUM(credit),0),2) FROM ledger").fetchone()

    guide = f"""# Golden Demo Guide

## الشركة
- {company_name}

## رحلة العرض المقترحة
1. افتح لوحة التحكم ثم العملاء والموردين والأصناف.
2. اعرض أمر الشراء ثم إذن الإضافة ثم فاتورة المورد.
3. اعرض أمر البيع ثم إذن الصرف ثم فاتورة البيع.
4. اعرض سند القبض وسند الصرف.
5. انتقل إلى كشف حساب العميل وكشف حساب المورد.
6. راجع اليومية ثم الأستاذ ثم ميزان المراجعة.

## البيانات الأساسية
- العميل الخاضع: `ID {subject_customer_id}`
- العميل العادي: `ID {normal_customer_id}`
- المورد الخاضع: `ID {taxable_supplier_id}`
- المورد المعفي: `ID {exempt_supplier_id}`

## المشتريات
- أمر شراء: `ID {purchase_order_id}` -> `/purchase-orders`
- إذن إضافة: `ID {purchase_receipt_id}` -> `/purchase-receipts`
- فاتورة مورد خاضعة: `ID {taxable_purchase_invoice_id}` -> `/purchases`
- فاتورة مورد معفاة: `ID {exempt_purchase_invoice_id}` -> `/purchases`

## المبيعات
- أمر بيع: `ID {sales_order_id}` -> `/sales-orders`
- إذن صرف: `ID {sales_delivery_id}` -> `/sales-deliveries`
- فاتورة بيع مخزنية: `ID {sales_invoice_id}` -> `/sales`
- فاتورة بيع مالية: `ID {financial_sales_invoice_id}` -> `/sales/financial`

## الخزينة
- سند قبض: `ID {receipt_id}` -> `/receipts`
- سند صرف: `ID {payment_id}` -> `/payments`

## روابط طباعة مباشرة
- فاتورة البيع: `/sales/{sales_invoice_id}/print`
- فاتورة المورد: `/purchases/{taxable_purchase_invoice_id}/print`
- أمر الشراء: `/purchase-orders/{purchase_order_id}/print`
- سند القبض: `/receipts/{receipt_id}/print`
- سند الصرف: `/payments/{payment_id}/print`

## تقارير المراجعة
- كشف حساب العميل الخاضع: `/customers/{subject_customer_id}/statement`
- كشف حساب المورد الخاضع: `/suppliers/{taxable_supplier_id}/statement`
- اليومية: `/journal`
- الأستاذ النقدي: `/ledger/1`
- ميزان المراجعة: `/trial-balance`
- تقرير العملاء: `/reports/customers`
- تقرير الموردين: `/reports/suppliers`
- تقرير المخزون: `/reports/inventory`

## فحص محاسبي سريع
- إجمالي المدين: `{trial_debit}`
- إجمالي الدائن: `{trial_credit}`
- الحالة: `{"متزن" if round(trial_debit, 2) == round(trial_credit, 2) else "غير متزن"}`
"""
    GUIDE_PATH.write_text(guide, encoding="utf-8")
    conn.close()


def main():
    seed_clean_demo.main()
    write_guide()
    print(f"Guide written: {GUIDE_PATH}")


if __name__ == "__main__":
    main()
