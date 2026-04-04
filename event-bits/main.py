"""
main.py
=======
Flöde:
  1. Beräkna potential event bits
  2. Dela event-fil i sektioner
  3. Mappa events → sektioner (med zon1/zon2)
  4. Filtrera bort no_event-only bitar
  5. Filtrera bort bitar som inte ändrats i BÅDA zonerna (om två finns)
     och inte är exklusiva för ETT event
  6. Skriv ut exklusiva bitar per event

Användning:
  python main.py <baseline_file> <event_file> <event_json>
"""

import sys

from analysis import get_potential_event_bits
from split_into_sections import (
    split_into_sections,
    build_section_ranges,
    assign_sections_to_events,
)

MASK_64 = (1 << 64) - 1

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

if len(sys.argv) != 4:
    print("Användning: python main.py <baseline_file> <event_file> <event_json>")
    sys.exit(1)

baseline_file = sys.argv[1]
event_file    = sys.argv[2]
event_json    = sys.argv[3]

# ---------------------------------------------------------------------------
# Hjälpfunktioner
# ---------------------------------------------------------------------------

def _parse_byte(val: str) -> int:
    val = val.strip()
    try:
        return int(val)
    except ValueError:
        return int(val, 16)


def _row_to_bits(row: dict) -> int:
    bits = 0
    for i in range(1, 9):
        bits = (bits << 8) | (_parse_byte(row[f"D{i}"]) & 0xFF)
    return bits


def _changed_bits(s0: int, s1: int) -> set[int]:
    mask = s0 & s1
    return {i + 1 for i in range(64) if (mask >> (63 - i)) & 1}


def _update_state(state: dict, id_val: str, bits: int):
    entry = state.get(id_val)
    if entry is None:
        entry = [0, 0]
        state[id_val] = entry
    entry[0] |= (~bits) & MASK_64
    entry[1] |= bits


def _build_state_for_sections(section_indices, sections, valid_ids) -> dict:
    state = {}
    for idx in section_indices:
        for row in sections[idx]:
            id_val = row["ID"]
            if id_val in valid_ids:
                _update_state(state, id_val, _row_to_bits(row))
    return state


def _filter_potential_event_bits(potential_event_bits, keep_fn):
    for id_val, peb in list(potential_event_bits.items()):
        filtered = [b for b in peb if keep_fn(id_val, b)]
        if filtered:
            potential_event_bits[id_val] = filtered
        else:
            del potential_event_bits[id_val]


# ---------------------------------------------------------------------------
# 1. Potential event bits
# ---------------------------------------------------------------------------

potential_event_bits = get_potential_event_bits(baseline_file, event_file)
valid_ids = set(potential_event_bits.keys())

# ---------------------------------------------------------------------------
# 2. Sektioner (i minnet)
# ---------------------------------------------------------------------------

sections       = split_into_sections(event_file)
section_ranges = build_section_ranges(sections)

# ---------------------------------------------------------------------------
# 3. Mappa events → sektioner
# ---------------------------------------------------------------------------

mapping       = assign_sections_to_events(section_ranges, event_json)
no_event_secs = set(mapping["no_event"]["sections"])
actual_events = {e: v for e, v in mapping.items() if e != "no_event" and v["sections"]}

# ---------------------------------------------------------------------------
# 4. Filtrera bort no_event-only bitar
# ---------------------------------------------------------------------------

state_no_event   = _build_state_for_sections(no_event_secs, sections, valid_ids)
state_all_events = _build_state_for_sections(
    [idx for v in actual_events.values() for idx in v["sections"]], sections, valid_ids
)

_filter_potential_event_bits(potential_event_bits, lambda id_val, bit:
    bit not in _changed_bits(*state_no_event.get(id_val, [0, 0]))
    or bit in _changed_bits(*state_all_events.get(id_val, [0, 0]))
)
valid_ids = set(potential_event_bits.keys())

# ---------------------------------------------------------------------------
# 5. Filtrera: biten måste ha ändrats i BÅDA zonerna (om zon2 finns)
#    och vara exklusiv för ETT event
# ---------------------------------------------------------------------------

state_per_event = {
    event_name: {
        "zone1": _build_state_for_sections(v["zone1"], sections, valid_ids),
        "zone2": _build_state_for_sections(v["zone2"], sections, valid_ids),
    }
    for event_name, v in actual_events.items()
}


def _changed_in_event(event_name: str, id_val: str, bit: int) -> bool:
    """True om biten ändrats i zon1, OCH i zon2 (om zon2 finns)."""
    z1 = state_per_event[event_name]["zone1"]
    z2 = state_per_event[event_name]["zone2"]
    in_zone1 = bit in _changed_bits(*z1.get(id_val, [0, 0]))
    if not actual_events[event_name]["zone2"]:
        return in_zone1
    in_zone2 = bit in _changed_bits(*z2.get(id_val, [0, 0]))
    return in_zone1 and in_zone2


_filter_potential_event_bits(potential_event_bits, lambda id_val, bit:
    sum(1 for e in actual_events if _changed_in_event(e, id_val, bit)) == 1
)

# ---------------------------------------------------------------------------
# 6. Räkna antal gånger varje exklusiv bit ändrats inom eventet
# ---------------------------------------------------------------------------

def _count_changes_in_sections(section_indices, id_val, bit):
    """Räknar antal gånger en bit skiftar värde (0→1 eller 1→0) inom sektionerna."""
    prev = None
    changes = 0
    for idx in section_indices:
        for row in sections[idx]:
            if row["ID"] != id_val:
                continue
            bits = _row_to_bits(row)
            val = (bits >> (64 - bit)) & 1
            if prev is not None and val != prev:
                changes += 1
            prev = val
    return changes


# ---------------------------------------------------------------------------
# 7. Skriv ut exklusiva bitar per event med antal förändringar
# ---------------------------------------------------------------------------

print("\nExklusiva bitar per event:")
for event_name, v in actual_events.items():
    print(f"\n  {event_name}:")
    found_any = False
    for id_val, peb in potential_event_bits.items():
        exclusive = [b for b in peb if _changed_in_event(event_name, id_val, b)]
        if exclusive:
            bit_info = ", ".join(
                f"b{b}({_count_changes_in_sections(v['sections'], id_val, b)})"
                for b in exclusive
            )
            print(f"    {id_val}: {bit_info}")
            found_any = True
    if not found_any:
        print("    Inga exklusiva bitar")