#!/usr/bin/env python3
"""
Test handling of empty fields in substitution files
"""

import re

def parse_csv_line(line: str):
    """Parse a CSV line preserving quotes"""
    # Split by comma, excluding commas within quotes
    COMMA_MATCHER = re.compile(r',(?=(?:[^"\']*["\'][^"\']*["\'])*[^"\']*$)')
    parts = COMMA_MATCHER.split(line)

    cleaned = []
    for part in parts:
        cleaned.append(part.strip())

    return cleaned

# Test the problematic line
test_line = '{ $(PLC_NAME),  CM00,  CP$(CP)4,  3,      TRIP_INT,          L900_SD_INT,              C$(CP)L900_SD_INT,            ,         1,     0,                              "LINAC Trip Integer"                      }'

# Remove the outer braces
content = test_line.strip()
if content.startswith('{') and content.endswith('}'):
    content = content[1:-1]

print("Original line:")
print(test_line)
print("\nParsed values:")

values = parse_csv_line(content)
for i, val in enumerate(values):
    if val == '':
        print(f"  Column {i}: [EMPTY]")
    else:
        print(f"  Column {i}: '{val}'")

print(f"\nTotal columns: {len(values)}")

# Check the specific empty field
print("\nThe empty field is at position 7")
print(f"Value before (position 6): '{values[6] if 6 < len(values) else 'N/A'}'")
print(f"Empty value (position 7): '{values[7] if 7 < len(values) else 'N/A'}'")
print(f"Value after (position 8): '{values[8] if 8 < len(values) else 'N/A'}'")

# Show what the correct fix would be
fixed_values = values.copy()
if 7 < len(fixed_values) and fixed_values[7] == '':
    fixed_values[7] = '""'

print("\nFixed line would be:")
fixed_line = '{ ' + ', '.join(fixed_values) + ' }'
print(fixed_line)