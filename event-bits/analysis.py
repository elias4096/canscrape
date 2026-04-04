"""
analysis.py
===========
Ersätter fyra tidigare moduler:
    baseline_noise.py
    static_bits.py
    find_noise_and_static.py
    potential_event_bits.py

Alla funktioner bygger på compute_bit_state() från bit_state.py,
så fil-läsningslogiken finns bara på ett ställe.
"""

from bit_state import compute_bit_state, MASK_64

ALL_BITS = set(range(1, 65))


# ---------------------------------------------------------------------------
# Interna hjälpfunktioner
# ---------------------------------------------------------------------------

def _changed_bits(seen_0: int, seen_1: int) -> list[int]:
    """Bitar som BÅDE sett 0 och 1 → har växlat."""
    mask = seen_0 & seen_1
    return [i + 1 for i in range(64) if (mask >> (63 - i)) & 1]


def _static_bits(seen_0: int, seen_1: int) -> list[int]:
    """Bitar som ALDRIG växlat (alltid 0 eller alltid 1)."""
    changed_mask = seen_0 & seen_1
    static_mask = (~changed_mask) & MASK_64
    return [i + 1 for i in range(64) if (static_mask >> (63 - i)) & 1]


def _bits_from_state(state: dict, extractor) -> dict:
    """Applicerar en extractor-funktion på varje ID i ett state-dict."""
    return {
        id_val: extractor(s0, s1)
        for id_val, (s0, s1) in state.items()
    }


# ---------------------------------------------------------------------------
# Publika funktioner
# ---------------------------------------------------------------------------

def get_noise_bits(baseline_file: str) -> dict:
    """
    Bitar som ändrats (minst en gång) i baseline-filen.
    Dessa räknas som bakgrundsbrus och ska exkluderas.

    Returnerar: { "ID": [bitnummer, ...] }
    """
    state = compute_bit_state(baseline_file)
    return _bits_from_state(state, _changed_bits)


def get_static_bits(event_file: str) -> dict:
    """
    Bitar som ALDRIG ändrats i event-filen.
    Dessa bär ingen information och ska exkluderas.

    Returnerar: { "ID": [bitnummer, ...] }
    """
    state = compute_bit_state(event_file)
    return _bits_from_state(state, _static_bits)


def get_noise_and_static(baseline_file: str, event_file: str) -> dict:
    """
    Unionen av noise-bitar (från baseline) och static-bitar (från event).
    Alla bitar i denna mängd är ointressanta för event-detektion.

    Returnerar: { "ID": [bitnummer, ...] }
    """
    noise  = get_noise_bits(baseline_file)
    static = get_static_bits(event_file)

    all_ids = set(noise) | set(static)
    return {
        id_val: sorted(set(noise.get(id_val, [])) | set(static.get(id_val, [])))
        for id_val in all_ids
    }


def get_potential_event_bits(baseline_file: str, event_file: str) -> dict:
    """
    Bitar som INTE är noise eller static → kandidater för event-signaler.

    Returnerar: { "ID": [bitnummer, ...] }
    """
    excluded = get_noise_and_static(baseline_file, event_file)
    return {
        id_val: sorted(ALL_BITS - set(bits))
        for id_val, bits in excluded.items()
        if ALL_BITS - set(bits)   # hoppa över tomma
    }