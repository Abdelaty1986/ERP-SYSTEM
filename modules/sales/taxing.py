DEFAULT_VAT_APPLICABLE = 1
DEFAULT_WITHHOLDING_APPLICABLE = 0
DEFAULT_VAT_RATE = 14.0
DEFAULT_WITHHOLDING_RATE = 0.0


def parse_flag(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "on", "yes"}


def parse_rate(value, default=0.0):
    try:
        parsed = float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        parsed = float(default or 0)
    return max(parsed, 0.0)


def taxable_line(subtotal, vat_enabled=True, withholding_enabled=False, vat_rate=DEFAULT_VAT_RATE, withholding_rate=DEFAULT_WITHHOLDING_RATE):
    subtotal = round(float(subtotal or 0), 2)
    vat_enabled = bool(vat_enabled)
    withholding_enabled = bool(withholding_enabled)
    vat_rate = parse_rate(vat_rate, DEFAULT_VAT_RATE if vat_enabled else 0.0)
    withholding_rate = parse_rate(withholding_rate, DEFAULT_WITHHOLDING_RATE)
    vat_amount = round(subtotal * vat_rate / 100, 2) if vat_enabled and vat_rate > 0 else 0.0
    withholding_amount = round(subtotal * withholding_rate / 100, 2) if withholding_enabled and withholding_rate > 0 else 0.0
    net_total = round(subtotal + vat_amount - withholding_amount, 2)
    return {
        "line_subtotal": subtotal,
        "subtotal": subtotal,
        "total": subtotal,
        "vat_applicable": 1 if vat_enabled else 0,
        "vat_enabled": 1 if vat_enabled else 0,
        "withholding_applicable": 1 if withholding_enabled else 0,
        "withholding_enabled": 1 if withholding_enabled else 0,
        "vat_rate": vat_rate if vat_enabled else 0.0,
        "withholding_rate": withholding_rate if withholding_enabled else 0.0,
        "vat_amount": vat_amount,
        "tax_amount": vat_amount,
        "withholding_amount": withholding_amount,
        "line_net": net_total,
        "net_total": net_total,
        "grand_total": net_total,
    }


def invoice_totals(lines):
    subtotal = round(sum(float(line.get("line_subtotal", line.get("subtotal", line.get("total", 0))) or 0) for line in lines), 2)
    vat_total = round(sum(float(line.get("vat_amount", line.get("tax_amount", 0)) or 0) for line in lines), 2)
    withholding_total = round(sum(float(line.get("withholding_amount", 0) or 0) for line in lines), 2)
    net_total = round(sum(float(line.get("line_net", line.get("net_total", line.get("grand_total", 0))) or 0) for line in lines), 2)
    return {
        "subtotal": subtotal,
        "total": subtotal,
        "vat_total": vat_total,
        "tax_amount": vat_total,
        "withholding_total": withholding_total,
        "withholding_amount": withholding_total,
        "net_total": net_total,
        "grand_total": net_total,
    }
