#!/usr/bin/env python3
# by kuronosuFear, updated for Python 3
import os
import struct
import binascii
import csv

def pad(s):
    rem = len(s) % 16
    if rem != 0:
        return s + b"\x00" * (16 - rem)
    return s + b"\x00" * 16

def process_dialogue_string(text_str):
    if text_str == 'NULL':
        return b'\x00'
    text_str = text_str.replace('\\n', '\n')
    if os.environ.get('SANGO_LEGACY_QUOTES') == '1':
        # old Japanese font had no ASCII ' and " glyphs: substitute look-alikes
        text_str = text_str.replace("'", '\u00b4')
        text_str = text_str.replace('"', '\u2033')
    # the French font (textures 6/7 of LINKDATA entry 0, see fr_patch/) has ' " and the ellipsis
    text_str = text_str.replace('...', '\u2026')
    return text_str.encode('utf-8') + b'\x00'

def read_tsv_grouped(tsv_path):
    if not os.path.exists(tsv_path):
        return {}
    groups = {}
    with open(tsv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        try:
            next(reader) # skip header
        except StopIteration:
            return {}
        for row in reader:
            if not row or row[0] == 'END':
                break
            filename = row[0]
            if filename not in groups:
                groups[filename] = []
            groups[filename].append(row)
    return groups

def type1recompile(out_dir):
    tsv_path = 'Sangokushi-script-Type1.tsv'
    grouped = read_tsv_grouped(tsv_path)
    for filename, rows in grouped.items():
        strings = []
        for r in rows:
            # Translated text is in column 6, fallback to original in column 5
            text = r[6] if len(r) > 6 and r[6] != '' else (r[5] if len(r) > 5 else '')
            strings.append(process_dialogue_string(text))

        num_strings = len(strings)
        file_table = struct.pack("<I", num_strings)
        data_offset = (num_strings * 8) + 4
        file_data = b''
        for s in strings:
            file_table += struct.pack("<2I", data_offset, len(s))
            data_offset += len(s)
            file_data += s

        out_path = os.path.join(out_dir, filename)
        with open(out_path, 'wb') as fo:
            fo.write(file_table + file_data)
        print(f'Generated: {filename}             ', end='\r', flush=True)
    print('\nType1 files done...')

def type2recompile(out_dir):
    tsv_path = 'Sangokushi-script-Type2.tsv'
    grouped = read_tsv_grouped(tsv_path)
    for filename, rows in grouped.items():
        # Group lines by entry index (column 3)
        entries_dict = {}
        for r in rows:
            entry_idx = int(r[3])
            if entry_idx not in entries_dict:
                entries_dict[entry_idx] = []
            text = r[6] if len(r) > 6 and r[6] != '' else (r[5] if len(r) > 5 else '')
            entries_dict[entry_idx].append(process_dialogue_string(text))

        num_entries = max(len(entries_dict), max(entries_dict.keys()) + 1 if entries_dict else 1)
        # Build entry bodies first
        entry_bodies = []
        for e_idx in range(num_entries):
            line_strings = entries_dict.get(e_idx, [])
            num_lines = len(line_strings)
            e_table = struct.pack("<I", num_lines)
            e_str_data = b''
            str_offset = 4 + num_lines * 8
            for s in line_strings:
                e_table += struct.pack("<2I", str_offset, len(s))
                str_offset += len(s)
                e_str_data += s
            entry_bodies.append(e_table + e_str_data)

        # Build main header and entry table
        header = struct.pack("<I", num_entries)
        curr_offset = 4 + num_entries * 8
        entry_headers = b''
        padded_bodies = []
        for body in entry_bodies:
            entry_headers += struct.pack("<2I", curr_offset, len(body))
            padded = body + b'\x00' * ((-len(body)) % 4)      # original files keep every entry 4-byte aligned
            padded_bodies.append(padded)
            curr_offset += len(padded)

        full_content = header + entry_headers + b''.join(padded_bodies)
        out_path = os.path.join(out_dir, filename)
        with open(out_path, 'wb') as fo:
            fo.write(full_content)
        print(f'Generated: {filename}             ', end='\r', flush=True)
    print('\nType2 files done...')

def type3recompile(out_dir):
    tsv_path = 'Sangokushi-script-Type3.tsv'
    grouped = read_tsv_grouped(tsv_path)
    for filename, rows in grouped.items():
        strings = []
        for r in rows:
            text = r[6] if len(r) > 6 and r[6] != '' else (r[5] if len(r) > 5 else '')
            hex_prefix = text[1:17] if len(text) >= 17 else '0000000000000000'
            dialogue_str = text[18:] if len(text) > 18 else ''
            tempy = process_dialogue_string(dialogue_str)
            prefix_bytes = binascii.unhexlify(hex_prefix)
            s4 = prefix_bytes + tempy
            strings.append(s4 + b'\x00' * ((-len(s4)) % 4))      # original Type 3 files: strings 4-byte aligned, no 16-byte padding

        num_strings = len(strings)
        file_table = b'\x62\x29\x00\x00' + struct.pack("<I", num_strings)
        data_offset = (num_strings * 4) + 8                      # offset table directly followed by the strings

        for s in strings:
            file_table += struct.pack("<I", data_offset)
            data_offset += len(s)

        body = b''.join(strings)
        if strings:                                              # the last string of an original file is not padded
            last = strings[-1]; body = body[:len(body) - len(last)] + last.rstrip(b'\x00') + b'\x00'
        full_content = file_table + body
        out_path = os.path.join(out_dir, filename)
        with open(out_path, 'wb') as fo:
            fo.write(full_content)
        print(f'Generated: {filename}             ', end='\r', flush=True)
    print('\nType3 files done...')

def type4recompile(out_dir):
    tsv_path = 'Sangokushi-script-Type4.tsv'
    grouped = read_tsv_grouped(tsv_path)
    for filename, rows in grouped.items():
        entry0_strings = []
        entry1_data = b''
        for r in rows:
            entry_type = r[3]
            text = r[6] if len(r) > 6 and r[6] != '' else (r[5] if len(r) > 5 else '')
            if entry_type == '1':
                parts = text.split(';')
                if len(parts) >= 2:
                    entry1_data = binascii.unhexlify(parts[1])
            else:
                entry0_strings.append(process_dialogue_string(text))

        num_lines = len(entry0_strings)
        e0_table = struct.pack("<I", num_lines)
        e0_str_data = b''
        str_offset = 4 + num_lines * 8
        for s in entry0_strings:
            e0_table += struct.pack("<2I", str_offset, len(s))
            str_offset += len(s)
            e0_str_data += s
        e0_full = e0_table + e0_str_data

        e0_offset = 20 # 4 bytes entry count + 2 entries * 8 bytes
        e0_size = len(e0_full)
        e0_pad = b'\x00' * ((-e0_size) % 4)                  # original files keep entry 1 4-byte aligned
        e1_offset = e0_offset + e0_size + len(e0_pad)
        e1_size = len(entry1_data)

        header = struct.pack("<I", 2) + struct.pack("<2I", e0_offset, e0_size) + struct.pack("<2I", e1_offset, e1_size)
        full_content = header + e0_full + e0_pad + entry1_data

        out_path = os.path.join(out_dir, filename)
        with open(out_path, 'wb') as fo:
            fo.write(full_content)
        print(f'Generated: {filename}             ', end='\r', flush=True)
    print('\nType4 files done...')

def main():
    path = 'Sangokushi-Translated'
    os.makedirs(path, exist_ok=True)

    type1recompile(path)
    type2recompile(path)
    type3recompile(path)
    type4recompile(path)

    print("All translated files compiled successfully!")

if __name__ == '__main__':
    main()