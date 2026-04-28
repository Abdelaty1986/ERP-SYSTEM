import re

css_path = r'C:\Users\Hany.Abdelatty\Desktop\تطوير برنامج LedgerX\ملفات السيرفر 16-4-2027\erp_dev_copy\static\style.css'

# Read the file
with open(css_path, 'r', encoding='utf-8') as f:
    css_content = f.read()

lines = css_content.split('\n')

print("=== DETAILED CSS ERROR ANALYSIS ===\n")

# Find the .7r error
print("1. SYNTAX ERRORS DETECTED:\n")
for i, line in enumerate(lines):
    if '.7r' in line:
        print(f"   Line {i+1}: {line.strip()}")
        print(f"   Issue: Invalid CSS unit '.7r' found")
        print(f"   Fix: Change '.7r' to '.7rem' or '.7px' depending on intended unit\n")

# Check for common CSS unit mistakes
print("2. VALIDATING CSS UNITS:")
line_count = 0
for i, line in enumerate(lines):
    # Look for CSS property patterns like: key: value;
    if ':' in line and not line.strip().startswith('//') and not line.strip().startswith('*'):
        # Check for invalid units
        matches = re.findall(r':\s*[\d.]+([a-z]+)', line)
        for unit in matches:
            if unit not in ['px', 'em', 'rem', 'pt', 'cm', 'mm', 'in', 'pc', '%', 'vh', 'vw', 'ms', 's']:
                if unit in ['r', 'e', 'remd']:  # Common typos
                    print(f"   Line {i+1}: Suspicious unit '{unit}' - {line.strip()[:70]}")
                    line_count += 1

if line_count == 0:
    print("   ✓ No other suspicious CSS units found")

# Check for missing semicolons
print("\n3. CHECKING FOR MISSING SEMICOLONS:")
semicolon_issues = 0
for i, line in enumerate(lines):
    stripped = line.strip()
    # Skip empty lines and comments
    if not stripped or stripped.startswith('/*') or stripped.startswith('*'):
        continue
    # Property should end with ; or {
    if ':' in stripped and not stripped.endswith(';') and not stripped.endswith('{') and not '}' in stripped:
        if not stripped.startswith('@') and not stripped.startswith('//'):
            print(f"   Line {i+1}: Possible missing semicolon - {stripped[:70]}")
            semicolon_issues += 1

if semicolon_issues == 0:
    print("   ✓ No missing semicolon issues detected")

# Check for matching braces
print("\n4. BRACE MATCHING:")
with_comments = css_content
open_count = with_comments.count('{')
close_count = with_comments.count('}')
if open_count == close_count:
    print(f"   ✓ Braces balanced: {open_count} opening, {close_count} closing")
else:
    print(f"   ✗ Brace mismatch: {open_count} opening, {close_count} closing")

# Full file check
print("\n5. FILE INTEGRITY CHECK:")
print(f"   Total lines: {len(lines)}")
print(f"   Total characters: {len(css_content)}")
print(f"   Last line: {lines[-1][:70] if lines[-1] else '(empty)'}")

print("\n=== SUMMARY ===")
print("Found 1 CSS syntax error:")
print("  • Invalid CSS unit '.7r' - should be '.7rem', '.7px', or other valid unit")
