import re

css_path = r'C:\Users\Hany.Abdelatty\Desktop\تطوير برنامج LedgerX\ملفات السيرفر 16-4-2027\erp_dev_copy\static\style.css'

# Read the file
with open(css_path, 'r', encoding='utf-8') as f:
    css_content = f.read()

errors = []
warnings = []

# Remove comments for analysis
css_no_comments = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)

# Check 1: Count opening and closing braces
open_braces = css_no_comments.count('{')
close_braces = css_no_comments.count('}')
if open_braces != close_braces:
    errors.append(f"Brace mismatch: {open_braces} opening braces, {close_braces} closing braces")

# Check 2: Find lines without semicolons before closing braces
lines = css_content.split('\n')
for i, line in enumerate(lines):
    stripped = line.strip()
    # Skip comments and empty lines
    if stripped.startswith('/*') or stripped.startswith('*') or not stripped:
        continue
    # Check if line ends with property but not semicolon
    if ':' in stripped and not stripped.endswith(';') and not stripped.endswith('{') and not stripped.endswith(','):
        if '}' not in stripped:
            warnings.append(f"Line {i+1}: Possible missing semicolon: {stripped[:80]}")

# Check 3: Check for unclosed strings
single_quotes = re.findall(r"[^\\]'(?:[^'\\\\]|\\\\.)*[^\\]'", css_no_comments)
double_quotes = re.findall(r'[^\\]"(?:[^"\\\\]|\\\\.)*[^\\]"', css_no_comments)

# Check 4: Look for invalid CSS values (common mistakes)
invalid_patterns = [
    (r':\s*\d+r(?!\w)', "Invalid CSS unit"),
    (r':\s*\d+\.\d+r(?!\w)', "Invalid CSS unit (should be rem, px, etc.)"),
]

for pattern, msg in invalid_patterns:
    if re.search(pattern, css_no_comments):
        matches = re.finditer(pattern, css_no_comments)
        for match in matches:
            errors.append(f"Found {msg} at position {match.start()}: {match.group()}")

# Check 5: Look for very obvious syntax issues
if '.7r' in css_content:
    errors.append("Found '.7r' which appears to be invalid CSS unit (should be '.7rem', '.7px', etc.)")

# Check 6: Missing colon after selector
lines_with_selectors = [l.strip() for l in lines if '{' in l and ':' in l]
for line in lines_with_selectors:
    if not re.search(r':\s*[^}]+;', line):
        continue

# Print results
print("=== CSS VALIDATION REPORT ===\n")
print(f"Total lines: {len(lines)}")
print(f"Total characters: {len(css_content)}")
print(f"Opening braces: {open_braces}")
print(f"Closing braces: {close_braces}")

if errors:
    print(f"\n⚠️  ERRORS FOUND ({len(errors)}):")
    for i, error in enumerate(errors, 1):
        print(f"  {i}. {error}")
else:
    print("\n✓ No critical errors found!")

if warnings:
    print(f"\n⚠️  WARNINGS ({len(warnings)}):")
    for i, warning in enumerate(warnings[:10], 1):  # Show first 10
        print(f"  {i}. {warning}")
    if len(warnings) > 10:
        print(f"  ... and {len(warnings) - 10} more warnings")
else:
    print("\n✓ No warnings!")

print("\nRunning detailed line-by-line check...")
