# trc_to_csv.py
from __future__ import annotations
import csv, re, sys
from pathlib import Path
from typing import List, Optional, Tuple

# Grundordning (vi plockar ev. bort Extended/Dir om konstanta)
BASE_HEADERS = ["Message Number","Time Offset (ms)","ID","Extended","Dir","Bus","LEN",
                "D1","D2","D3","D4","D5","D6","D7","D8"]

line_re = re.compile(
    r"^\s*(\d+)\)\s+([0-9]+(?:\.[0-9]+)?)\s+(R|T)x\s+([0-9A-Fa-f]+)\s+(\d+)\s+(.*)$"
)

def _hex_bytes(s: str, n: int) -> List[str]:
    parts = [p.upper() for p in s.strip().split()[:n]]
    return parts + [""] * (8 - len(parts))

def _infer_extended(can_id_hex: str) -> bool:
    # 29-bit (extended) om värdet > 0x7FF (2047)
    try:
        val = int(can_id_hex, 16)
    except ValueError:
        val = 0
    return val > 0x7FF

def _format_id(can_id_hex: str, extended: bool) -> str:
    val = int(can_id_hex, 16)
    width = 8 if extended else 4
    return f"{val:0{width}X}"

def _parse_trc(trc_path: Path) -> List[dict]:
    rows = []
    with trc_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = line_re.match(line)
            if not m:
                continue
            msg_no_s, off_ms_s, dir_ch, can_id_hex, len_s, data_hex = m.groups()
            length = int(len_s)
            extended = _infer_extended(can_id_hex)
            rows.append({
                "Message Number": int(msg_no_s),
                "Time Offset (ms)": float(off_ms_s),
                "Dir": f"{dir_ch}x",
                "ID_raw": can_id_hex.upper(),
                "Extended": extended,
                "Bus": "0",
                "LEN": str(length),
                "DATA": _hex_bytes(data_hex, length),
            })
    return rows

def trc_to_csv(trc_path: Path, out_csv: Optional[Path] = None) -> Path:
    trc_path = Path(trc_path)
    out_csv = trc_path.with_suffix(".csv") if out_csv is None else Path(out_csv)

    rows = _parse_trc(trc_path)
    if not rows:
        raise ValueError("Inga meddelanden hittades i TRC-filen.")

    # Kolla om Extended och/eller Dir är konstanta
    ext_set = {r["Extended"] for r in rows}
    dir_set = {r["Dir"] for r in rows}
    drop_extended = (len(ext_set) == 1)
    drop_dir = (len(dir_set) == 1)

    # Bygg headers i rätt ordning
    headers = []
    for h in BASE_HEADERS:
        if h == "Extended" and drop_extended: 
            continue
        if h == "Dir" and drop_dir:
            continue
        headers.append(h)

    with out_csv.open("w", newline="", encoding="utf-8") as fout:
        w = csv.writer(fout)
        w.writerow(headers)
        for r in rows:
            # Formatera ID enligt Extended
            id_fmt = _format_id(r["ID_raw"], r["Extended"])
            out = []
            for h in headers:
                if h == "Message Number":
                    out.append(r["Message Number"])
                elif h == "Time Offset (ms)":
                    out.append(f"{r['Time Offset (ms)']:.1f}")
                elif h == "ID":
                    out.append(id_fmt)
                elif h == "Extended":
                    out.append(str(r["Extended"]))
                elif h == "Dir":
                    out.append(r["Dir"])
                elif h == "Bus":
                    out.append(r["Bus"])
                elif h == "LEN":
                    out.append(r["LEN"])
                else:
                    # D1..D8
                    if h.startswith("D"):
                        idx = int(h[1:]) - 1
                        out.append(r["DATA"][idx])
            w.writerow(out)
    return out_csv

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trc_to_csv.py <input.trc> [output.csv]")
        sys.exit(1)
    inp = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) >= 3 else None
    print(trc_to_csv(inp, out))
