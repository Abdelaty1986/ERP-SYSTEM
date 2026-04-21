import sqlite3
from pathlib import Path


DB = Path(__file__).with_name("database.db")


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS company_settings(
            id INTEGER PRIMARY KEY CHECK(id = 1),
            company_name TEXT NOT NULL DEFAULT 'شركة تجريبية للصناعات',
            tax_number TEXT,
            commercial_register TEXT,
            address TEXT,
            phone TEXT,
            email TEXT,
            default_tax_rate REAL NOT NULL DEFAULT 14,
            invoice_footer TEXT
        )
        """
    )
    cur.execute(
        """
        INSERT INTO company_settings(
            id,company_name,tax_number,commercial_register,address,phone,email,default_tax_rate,invoice_footer
        )
        VALUES (1,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            company_name=excluded.company_name,
            tax_number=excluded.tax_number,
            commercial_register=excluded.commercial_register,
            address=excluded.address,
            phone=excluded.phone,
            email=excluded.email,
            default_tax_rate=excluded.default_tax_rate,
            invoice_footer=excluded.invoice_footer
        """,
        (
            "شركة تجريبية للصناعات",
            "000-000-000",
            "123456",
            "القاهرة - جمهورية مصر العربية",
            "01000000000",
            "info@example.com",
            14,
            "شكراً لتعاملكم معنا",
        ),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
