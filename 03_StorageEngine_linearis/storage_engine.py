import os
import struct


class StorageEngine:
    def __init__(self, filename="data.bin", record_size=64):
        if record_size <= 8:
            raise ValueError("A rekordméretnek nagyobbnak kell lennie 8 bájtnál (8 bájt az ID).")
        self.filename = filename
        self.record_size = record_size
        self.string_size = record_size - 8

        self.record_format = f">q{self.string_size}s"

        if not os.path.exists(self.filename):
            with open(self.filename, "wb"):
                pass

    def write_record(self, record_id: int, name: str):
        if record_id < 0:
            raise ValueError("Az ID nem lehet negatív.")
        encoded_name = name.encode("utf-8")[: self.string_size].ljust(self.string_size, b"\x00")
        binary_data = struct.pack(self.record_format, record_id, encoded_name)
        offset = record_id * self.record_size

        with open(self.filename, "rb+") as f:
            f.seek(offset)
            f.write(binary_data)
            f.flush()

    def read_record(self, record_id: int):
        offset = record_id * self.record_size

        if record_id < 0 or os.path.getsize(self.filename) < offset + self.record_size:
            return None

        with open(self.filename, "rb") as f:
            f.seek(offset)
            data = f.read(self.record_size)

        rec_id, raw_name = struct.unpack(self.record_format, data)
        clean_name = raw_name.rstrip(b"\x00").decode("utf-8", errors="ignore")
        return {"id": rec_id, "name": clean_name}

    def read_all_records(self):
        records = []
        total_records = os.path.getsize(self.filename) // self.record_size
        for record_id in range(total_records):
            rec = self.read_record(record_id)
            if rec and rec["name"]:
                records.append(rec)
        return records


    def delete_record(self, record_id: int, compact: bool = True) -> bool:
        rec = self.read_record(record_id)
        if rec is None or not rec["name"]:
            return False

        offset = record_id * self.record_size
        with open(self.filename, "rb+") as f:
            f.seek(offset)
            f.write(b"\x00" * self.record_size)
            f.flush()

        if compact:
            self._truncate_trailing_empty()
        return True

    def _truncate_trailing_empty(self):
        """A fájl végén lévő üres (csupa 0x00) rekordok levágása."""
        total = os.path.getsize(self.filename) // self.record_size
        with open(self.filename, "rb+") as f:
            last_used = -1
            for rid in range(total - 1, -1, -1):
                f.seek(rid * self.record_size)
                if f.read(self.record_size).strip(b"\x00"):
                    last_used = rid
                    break
            f.truncate((last_used + 1) * self.record_size)

    def hexdump(self, max_records=None, only_used=False):
        """Hexa-szerkesztő szerű nézet, rekordonként tagolva."""
        size = os.path.getsize(self.filename)
        total = size // self.record_size
        if max_records is not None:
            total = min(total, max_records)
        with open(self.filename, "rb") as f:
            for rid in range(total):
                f.seek(rid * self.record_size)
                rec = f.read(self.record_size)
                empty = not rec.strip(b"\x00")
                if only_used and empty:
                    continue
                print(f"-- rekord #{rid} (offset {rid * self.record_size}, "
                      f"{'ÜRES' if empty else 'foglalt'})")
                for i in range(0, len(rec), 16):
                    chunk = rec[i:i + 16]
                    hx = " ".join(f"{b:02X}" for b in chunk)
                    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                    print(f"   {rid * self.record_size + i:08X}  {hx:<47}  |{asc}|")
