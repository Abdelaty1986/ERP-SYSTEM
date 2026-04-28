import os

css_path = r'C:\Users\Hany.Abdelatty\Desktop\تطوير برنامج LedgerX\ملفات السيرفر 16-4-2027\erp_dev_copy\static\style.css'

# Read the file
with open(css_path, 'r', encoding='utf-8') as f:
    css_content = f.read()

print("=== CSS File Content ===")
print(css_content[:5000])
print("\n... (file continues)")
print(f"\nTotal file size: {len(css_content)} characters")
