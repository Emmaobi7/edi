"""
Compare generated EDI against boss's expected output.
"""
import json

# Boss's expected output
boss_output = [
    "BIG*20240827*6GYNT 2*****PP*00",
    "N1*BT**10*WWWWWW**TO",
    "N1*II**M4*AJ2**FR",
    "N1*II**10",
    "LM*DF",
    "LQ*0*FS2",
    "FA1*DZ",
    "FA2*58*97X12345678",
    "FA2*18*2142020",
    "IT1*1*5*PK*362.34*ST*FS*6515015616204",
    "REF*TN*WWWWWW42290001",
    "DTM*168*20240827",
    "CAD*****Z",
    "SAC*C*D350***181170",
    "TDS*181170",
    "CTT*1"
]

# Load generated output
with open('test_output.json') as f:
    data = json.load(f)
    generated = [seg.rstrip('~') for seg in data['raw_edi_segments']]

print("=" * 70)
print("COMPARISON: Generated vs Boss's Output")
print("=" * 70)
print()

# Track matches
matches = []
missing = []
extra = []

for i, boss_seg in enumerate(boss_output, 1):
    if boss_seg in generated:
        print(f"{i:2}. ✓ {boss_seg}")
        matches.append(boss_seg)
    else:
        print(f"{i:2}. ✗ {boss_seg}")
        print(f"      ^^ MISSING FROM GENERATED OUTPUT")
        missing.append(boss_seg)

print()
print("=" * 70)
print("EXTRA SEGMENTS (not in boss's output):")
print("=" * 70)
for seg in generated:
    if seg not in boss_output:
        print(f"  + {seg}")
        extra.append(seg)

print()
print("=" * 70)
print(f"RESULTS:")
print("=" * 70)
print(f"  Matches: {len(matches)}/{len(boss_output)}")
print(f"  Missing: {len(missing)}")
print(f"  Extra:   {len(extra)}")
print()

if missing:
    print("Missing segments:")
    for seg in missing:
        print(f"  - {seg}")
    print()

if extra:
    print("Extra segments:")
    for seg in extra:
        print(f"  + {seg}")
    print()

# Calculate accuracy
accuracy = (len(matches) / len(boss_output)) * 100
print(f"Accuracy: {accuracy:.1f}%")
