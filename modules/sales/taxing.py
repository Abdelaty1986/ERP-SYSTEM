def parse_flag(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "on", "yes"}


def taxable_line(subtotal, vat_enabled=True, withholding_enabled=False, vat_rate=14, withholding_rate=1):
    subtotal = float(subtotal or 0)
    vat_rate = float(vat_rate or 0)
    withholding_rate = float(withholding_rate or 0)
    vat_enabled = bool(vat_enabled)
    withholding_enabled = bool(withholding_enabled)
    vat_amount = round(subtotal * vat_rate / 100, 2) if vat_enabled and vat_rate > 0 else 0.0
    withholding_amount = round(subtotal * withholding_rate / 100, 2) if withholding_enabled and withholding_rate > 0 else 0.0
    grand_total = round(subtotal + vat_amount, 2)
    return {
        "subtotal": round(subtotal, 2),
        "vat_enabled": 1 if vat_enabled else 0,
        "withholding_enabled": 1 if withholding_enabled else 0,
        "vat_rate": vat_rate if vat_enabled else 0.0,
        "withholding_rate": withholding_rate if withholding_enabled else 0.0,
        "vat_amount": vat_amount,
        "withholding_amount": withholding_amount,
        "grand_total": grand_total,
    }


def invoice_totals(lines):
    return {
        "total": round(sum(line["subtotal"] for line in lines), 2),
        "tax_amount": round(sum(line["vat_amount"] for line in lines), 2),
        "withholding_amount": round(sum(line["withholding_amount"] for line in lines), 2),
        "grand_total": round(sum(line["grand_total"] for line in lines), 2),
    }
