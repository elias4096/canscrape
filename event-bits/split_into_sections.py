import csv
import json


def split_into_sections(csv_file_path):
    rows = []
    all_ids = set()

    with open(csv_file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        has_msg_num = 'Message Number' in fieldnames
        has_extended = 'Extended' in fieldnames

        for idx, row in enumerate(reader):
            if not has_msg_num:
                row['Message Number'] = str(idx)

            val = row['ID'].strip().upper()
            id_int = int(val, 16)
            row['ID'] = format(id_int & 0x7FF, '04X')

            rows.append(row)
            all_ids.add(row['ID'])

    sections = []
    current_section = []
    seen_ids = set()

    for row in rows:
        current_section.append(row)
        seen_ids.add(row['ID'])

        if seen_ids == all_ids:
            sections.append(current_section)
            current_section = []
            seen_ids = set()

    return sections


def build_section_ranges(sections):
    section_ranges = []
    for i, section in enumerate(sections):
        start_msg = int(section[0]['Message Number'])
        end_msg = int(section[-1]['Message Number'])
        section_ranges.append((i, start_msg, end_msg))
    return section_ranges


def overlaps(s_start, s_end, e_start, e_end):
    return s_start <= e_end and s_end >= e_start


def assign_sections_to_events(section_ranges, json_path):
    with open(json_path, encoding='utf-8') as f:
        events = json.load(f)

    result = {}
    all_assigned_sections = set()

    for event_name, data in events.items():
        # Collect all (start, end) pairs dynamically: start_index, start_index_2, start_index_3 ...
        pairs = []
        # First pair (no suffix)
        s = data.get("start_index", 0)
        e = data.get("end_index", 0)
        if s and e:
            pairs.append((s, e))
        # Subsequent pairs (_2, _3, ...)
        i = 2
        while True:
            s = data.get(f"start_index_{i}", 0)
            e = data.get(f"end_index_{i}", 0)
            if not s and not e:
                break
            if s and e:
                pairs.append((s, e))
            i += 1

        # Each pair becomes its own zone
        zones = []
        for start, end in pairs:
            zone = set()
            for sec_idx, s_start, s_end in section_ranges:
                if overlaps(s_start, s_end, start, end):
                    zone.add(sec_idx)
            zones.append(sorted(zone))

        all_secs = set(sec for zone in zones for sec in zone)
        result[event_name] = {
            "sections": sorted(all_secs),
            "zones":    zones,
        }
        all_assigned_sections.update(all_secs)

    # no_event
    all_sections = set(sec_idx for sec_idx, _, _ in section_ranges)
    no_event_sections = sorted(all_sections - all_assigned_sections)
    result["no_event"] = {
        "sections": no_event_sections,
        "zones":    [no_event_sections],
    }

    return result


def write_sectioned_csv(input_csv_path, sections, output_csv_path):
    with open(input_csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        original_headers = list(reader.fieldnames or [])

    if 'Message Number' not in original_headers:
        original_headers = ['Message Number'] + original_headers

    new_headers = ["Section"] + original_headers

    with open(output_csv_path, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=new_headers)
        writer.writeheader()

        for section_idx, section in enumerate(sections):
            for row in section:
                new_row = {"Section": section_idx}
                new_row.update(row)
                writer.writerow(new_row)


def run_pipeline(csv_path, json_path, output_csv_path=None):
    sections = split_into_sections(csv_path)
    section_ranges = build_section_ranges(sections)
    mapping = assign_sections_to_events(section_ranges, json_path)

    if output_csv_path:
        write_sectioned_csv(csv_path, sections, output_csv_path)

    return sections, section_ranges, mapping


if __name__ == "__main__":
    csv_path = "raw-export.csv"
    json_path = "event_indexes.json"

    sections, section_ranges, mapping = run_pipeline(csv_path, json_path)

    for event, v in mapping.items():
        print(f"{event}: {v['sections']}")