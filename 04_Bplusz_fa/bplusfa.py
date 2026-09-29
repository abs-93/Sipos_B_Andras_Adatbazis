import os
import struct
import sys

PAGE_SIZE = 256
NODE_TYPE_INTERNAL = 0
NODE_TYPE_LEAF = 1
NODE_TYPE_FREE = 2

HEADER_FORMAT = ">BBiH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

RECORD_FORMAT = ">q40s"
RECORD_SIZE = struct.calcsize(RECORD_FORMAT)


MAX_LEAF_RECORDS = 3
MAX_INTERNAL_KEYS = 5

MIN_LEAF_RECORDS = 1
MIN_INTERNAL_KEYS = 2


class DiskBPlusTreeVisualizer:
    def __init__(self, filename="data.bin"):
        self.filename = filename
        self.page_reads = 0
        if not os.path.exists(self.filename) or os.path.getsize(self.filename) == 0:
            with open(self.filename, "wb") as f:
                f.write(b'\x00' * PAGE_SIZE)
            self._write_page_header(0, NODE_TYPE_LEAF, num_keys=0, next_page_id=-1)


    def _get_page_offset(self, page_id: int) -> int:
        return page_id * PAGE_SIZE

    def _allocate_page(self) -> int:
        total_pages = os.path.getsize(self.filename) // PAGE_SIZE
        for p in range(1, total_pages):
            if self._read_page_header(p)[0] == NODE_TYPE_FREE:
                with open(self.filename, "rb+") as f:
                    f.seek(self._get_page_offset(p))
                    f.write(b'\x00' * PAGE_SIZE)
                return p
        new_page_id = total_pages
        with open(self.filename, "a+b") as f:
            f.write(b'\x00' * PAGE_SIZE)
        return new_page_id

    def _free_page(self, page_id: int):
        with open(self.filename, "rb+") as f:
            f.seek(self._get_page_offset(page_id))
            f.write(b'\x00' * PAGE_SIZE)
        self._write_page_header(page_id, NODE_TYPE_FREE, 0, -1)

    def _read_page_header(self, page_id: int):
        with open(self.filename, "rb") as f:
            f.seek(self._get_page_offset(page_id))
            data = f.read(HEADER_SIZE)
        node_type, num_keys, next_page_id, _ = struct.unpack(HEADER_FORMAT, data)
        return node_type, num_keys, next_page_id

    def _write_page_header(self, page_id: int, node_type: int, num_keys: int, next_page_id: int = -1):
        with open(self.filename, "rb+") as f:
            f.seek(self._get_page_offset(page_id))
            data = struct.pack(HEADER_FORMAT, node_type, num_keys, next_page_id, 0)
            f.write(data)

    def _read_leaf_records(self, page_id: int, num_keys: int):
        records = []
        with open(self.filename, "rb") as f:
            f.seek(self._get_page_offset(page_id) + HEADER_SIZE)
            for _ in range(num_keys):
                raw = f.read(RECORD_SIZE)
                rec_id, raw_name = struct.unpack(RECORD_FORMAT, raw)
                clean_name = raw_name.rstrip(b'\x00').decode('utf-8', errors='ignore')
                records.append((rec_id, clean_name))
        return records

    def _write_leaf_records(self, page_id: int, records, next_page_id=None):
        page_data = bytearray(PAGE_SIZE)
        if next_page_id is None:
            _, _, next_page_id = self._read_page_header(page_id)

        header = struct.pack(HEADER_FORMAT, NODE_TYPE_LEAF, len(records), next_page_id, 0)
        page_data[0:HEADER_SIZE] = header

        offset = HEADER_SIZE
        for rec_id, name in records:
            encoded_name = name.encode('utf-8')[:40].ljust(40, b'\x00')
            rec_bytes = struct.pack(RECORD_FORMAT, rec_id, encoded_name)
            page_data[offset:offset + RECORD_SIZE] = rec_bytes
            offset += RECORD_SIZE

        with open(self.filename, "rb+") as f:
            f.seek(self._get_page_offset(page_id))
            f.write(page_data)

    def _read_internal_keys(self, page_id: int, num_keys: int):
        keys = []
        children = []
        with open(self.filename, "rb") as f:
            f.seek(self._get_page_offset(page_id) + HEADER_SIZE)
            for _ in range(num_keys):
                child_id, key = struct.unpack(">iq", f.read(12))
                children.append(child_id)
                keys.append(key)
            last_child = struct.unpack(">i", f.read(4))[0]
            children.append(last_child)
        return keys, children

    def _write_internal_keys(self, page_id: int, keys, children):
        page_data = bytearray(PAGE_SIZE)

        header = struct.pack(HEADER_FORMAT, NODE_TYPE_INTERNAL, len(keys), -1, 0)
        page_data[0:HEADER_SIZE] = header

        offset = HEADER_SIZE
        for i in range(len(keys)):
            item_bytes = struct.pack(">iq", children[i], keys[i])
            page_data[offset:offset + 12] = item_bytes
            offset += 12

        last_child_bytes = struct.pack(">i", children[-1])
        page_data[offset:offset + 4] = last_child_bytes

        with open(self.filename, "rb+") as f:
            f.seek(self._get_page_offset(page_id))
            f.write(page_data)


    def _load(self, page_id: int):
        self.page_reads += 1
        n_type, num_keys, next_p = self._read_page_header(page_id)
        if n_type == NODE_TYPE_LEAF:
            return n_type, self._read_leaf_records(page_id, num_keys), next_p
        keys, children = self._read_internal_keys(page_id, num_keys)
        return n_type, (keys, children), next_p


    def insert(self, rec_id: int, name: str):
        if self._update_if_exists(rec_id, name):
            return

        root_type, root_keys, _ = self._read_page_header(0)

        if (root_type == NODE_TYPE_LEAF and root_keys >= MAX_LEAF_RECORDS) or \
           (root_type == NODE_TYPE_INTERNAL and root_keys >= MAX_INTERNAL_KEYS):

            new_root_id = self._allocate_page()

            with open(self.filename, "rb+") as f:
                f.seek(0)
                root_bytes = f.read(PAGE_SIZE)
                f.seek(self._get_page_offset(new_root_id))
                f.write(root_bytes)

            with open(self.filename, "rb+") as f:
                f.seek(0)
                f.write(b'\x00' * PAGE_SIZE)


            self._write_internal_keys(0, [], [new_root_id])
            self._split_child(0, 0, new_root_id)
            self._insert_non_full(0, rec_id, name)
        else:
            self._insert_non_full(0, rec_id, name)

    def _update_if_exists(self, rec_id, name):
        leaf_id, _ = self._find_leaf(rec_id)
        _, num_keys, nxt = self._read_page_header(leaf_id)
        records = self._read_leaf_records(leaf_id, num_keys)
        for i, (k, _) in enumerate(records):
            if k == rec_id:
                records[i] = (rec_id, name)
                self._write_leaf_records(leaf_id, records, nxt)
                return True
        return False

    def _insert_non_full(self, page_id: int, rec_id: int, name: str):
        node_type, num_keys, _ = self._read_page_header(page_id)

        if node_type == NODE_TYPE_LEAF:
            records = self._read_leaf_records(page_id, num_keys)
            records.append((rec_id, name))
            records.sort(key=lambda x: x[0])
            self._write_leaf_records(page_id, records)
        else:
            keys, children = self._read_internal_keys(page_id, num_keys)
            i = 0
            while i < len(keys) and rec_id >= keys[i]:
                i += 1

            child_id = children[i]
            c_type, c_keys, _ = self._read_page_header(child_id)

            if (c_type == NODE_TYPE_LEAF and c_keys >= MAX_LEAF_RECORDS) or \
               (c_type == NODE_TYPE_INTERNAL and c_keys >= MAX_INTERNAL_KEYS):
                self._split_child(page_id, i, child_id)
                keys, children = self._read_internal_keys(page_id, self._read_page_header(page_id)[1])
                if rec_id >= keys[i]:
                    child_id = children[i + 1]

            self._insert_non_full(child_id, rec_id, name)

    def _split_child(self, parent_id: int, index: int, child_id: int):
        c_type, c_num_keys, c_next = self._read_page_header(child_id)
        new_child_id = self._allocate_page()

        p_keys, p_children = self._read_internal_keys(parent_id, self._read_page_header(parent_id)[1])

        if c_type == NODE_TYPE_LEAF:
            records = self._read_leaf_records(child_id, c_num_keys)
            mid = len(records) // 2

            left_recs = records[:mid]
            right_recs = records[mid:]

            self._write_leaf_records(child_id, left_recs, new_child_id)
            self._write_leaf_records(new_child_id, right_recs, c_next)

            p_keys.insert(index, right_recs[0][0])
            p_children.insert(index + 1, new_child_id)
        else:
            keys, children = self._read_internal_keys(child_id, c_num_keys)
            mid = len(keys) // 2

            split_key = keys[mid]

            self._write_internal_keys(child_id, keys[:mid], children[:mid + 1])
            self._write_internal_keys(new_child_id, keys[mid + 1:], children[mid + 1:])

            p_keys.insert(index, split_key)
            p_children.insert(index + 1, new_child_id)

        self._write_internal_keys(parent_id, p_keys, p_children)


    def _find_leaf(self, key: int):
        path = []
        page_id = 0
        while True:
            n_type, num_keys, _ = self._read_page_header(page_id)
            path.append(page_id)
            if n_type == NODE_TYPE_LEAF:
                return page_id, path
            keys, children = self._read_internal_keys(page_id, num_keys)
            i = 0
            while i < len(keys) and key >= keys[i]:
                i += 1
            page_id = children[i]

    def search(self, key: int, verbose: bool = True):
        steps = 0
        page_id = 0
        if verbose:
            print(f"\n[KERESÉS] ID = {key}")
        while True:
            n_type, content, _ = self._load(page_id)
            steps += 1
            if n_type == NODE_TYPE_LEAF:
                ids = [r[0] for r in content]
                if verbose:
                    print(f"  {steps}. lépés: Page {page_id} [LEVÉL]  rekordok={ids}")
                for rec_id, name in content:
                    if rec_id == key:
                        if verbose:
                            print(f"  >>> TALÁLAT {steps} lépésben: ID={rec_id}, Név='{name}'")
                        return (rec_id, name), steps
                if verbose:
                    print(f"  >>> NINCS ilyen rekord ({steps} lépés)")
                return None, steps

            keys, children = content
            i = 0
            while i < len(keys) and key >= keys[i]:
                i += 1
            if verbose:
                print(f"  {steps}. lépés: Page {page_id} [BELSŐ] kulcsok={keys} "
                      f"-> {i}. ág -> Page {children[i]}")
            page_id = children[i]

    def range_search(self, low: int, high: int):
        leaf_id, path = self._find_leaf(low)
        steps = len(path)
        result = []
        while leaf_id != -1:
            _, num_keys, nxt = self._read_page_header(leaf_id)
            for rec_id, name in self._read_leaf_records(leaf_id, num_keys):
                if rec_id > high:
                    return result, steps
                if rec_id >= low:
                    result.append((rec_id, name))
            leaf_id = nxt
            if leaf_id != -1:
                steps += 1
        return result, steps



    def delete(self, key: int, verbose: bool = True) -> bool:
        self._log = [] if verbose else None
        found = self._delete_rec(0, key)
        if found:
            self._shrink_root()
        if verbose:
            print(f"\n[TÖRLÉS] ID = {key}: {'törölve' if found else 'NINCS ilyen rekord'}")
            for line in self._log:
                print("   - " + line)
        return found

    def _note(self, msg):
        if self._log is not None:
            self._log.append(msg)

    def _delete_rec(self, page_id: int, key: int) -> bool:
        n_type, num_keys, nxt = self._read_page_header(page_id)

        if n_type == NODE_TYPE_LEAF:
            records = self._read_leaf_records(page_id, num_keys)
            new_records = [r for r in records if r[0] != key]
            if len(new_records) == len(records):
                return False
            self._write_leaf_records(page_id, new_records, nxt)
            self._note(f"rekord eltávolítva a Page {page_id} levélből")
            return True

        keys, children = self._read_internal_keys(page_id, num_keys)
        i = 0
        while i < len(keys) and key >= keys[i]:
            i += 1
        found = self._delete_rec(children[i], key)
        if found:
            self._fix_underflow(page_id, i)
        return found

    def _is_underflow(self, page_id):
        n_type, num_keys, _ = self._read_page_header(page_id)
        if n_type == NODE_TYPE_LEAF:
            return num_keys < MIN_LEAF_RECORDS
        return num_keys < MIN_INTERNAL_KEYS

    def _can_lend(self, page_id):
        n_type, num_keys, _ = self._read_page_header(page_id)
        if n_type == NODE_TYPE_LEAF:
            return num_keys > MIN_LEAF_RECORDS
        return num_keys > MIN_INTERNAL_KEYS

    def _fix_underflow(self, parent_id: int, idx: int):
        p_keys, p_children = self._read_internal_keys(parent_id, self._read_page_header(parent_id)[1])
        child = p_children[idx]
        if not self._is_underflow(child):
            return

        left = p_children[idx - 1] if idx > 0 else None
        right = p_children[idx + 1] if idx + 1 < len(p_children) else None
        c_type = self._read_page_header(child)[0]

        if left is not None and self._can_lend(left):
            self._borrow_from_left(parent_id, idx, c_type)
        elif right is not None and self._can_lend(right):
            self._borrow_from_right(parent_id, idx, c_type)
        elif left is not None:
            self._merge(parent_id, idx - 1, c_type)
        else:
            self._merge(parent_id, idx, c_type)

    def _borrow_from_left(self, parent_id, idx, c_type):
        p_keys, p_children = self._read_internal_keys(parent_id, self._read_page_header(parent_id)[1])
        left, child = p_children[idx - 1], p_children[idx]
        if c_type == NODE_TYPE_LEAF:
            _, ln, lnext = self._read_page_header(left)
            _, cn, cnext = self._read_page_header(child)
            l_recs = self._read_leaf_records(left, ln)
            c_recs = self._read_leaf_records(child, cn)
            moved = l_recs.pop()
            c_recs.insert(0, moved)
            self._write_leaf_records(left, l_recs, lnext)
            self._write_leaf_records(child, c_recs, cnext)
            p_keys[idx - 1] = c_recs[0][0]
            self._note(f"kölcsönzés: ID={moved[0]} a bal testvérből (Page {left} -> Page {child})")
        else:
            l_keys, l_ch = self._read_internal_keys(left, self._read_page_header(left)[1])
            c_keys, c_ch = self._read_internal_keys(child, self._read_page_header(child)[1])
            c_keys.insert(0, p_keys[idx - 1])
            c_ch.insert(0, l_ch.pop())
            p_keys[idx - 1] = l_keys.pop()
            self._write_internal_keys(left, l_keys, l_ch)
            self._write_internal_keys(child, c_keys, c_ch)
            self._note(f"kölcsönzés (belső): kulcsforgatás a bal testvéren át (Page {left} -> Page {child})")
        self._write_internal_keys(parent_id, p_keys, p_children)

    def _borrow_from_right(self, parent_id, idx, c_type):
        p_keys, p_children = self._read_internal_keys(parent_id, self._read_page_header(parent_id)[1])
        child, right = p_children[idx], p_children[idx + 1]
        if c_type == NODE_TYPE_LEAF:
            _, cn, cnext = self._read_page_header(child)
            _, rn, rnext = self._read_page_header(right)
            c_recs = self._read_leaf_records(child, cn)
            r_recs = self._read_leaf_records(right, rn)
            moved = r_recs.pop(0)
            c_recs.append(moved)
            self._write_leaf_records(child, c_recs, cnext)
            self._write_leaf_records(right, r_recs, rnext)
            p_keys[idx] = r_recs[0][0]
            self._note(f"kölcsönzés: ID={moved[0]} a jobb testvérből (Page {right} -> Page {child})")
        else:
            c_keys, c_ch = self._read_internal_keys(child, self._read_page_header(child)[1])
            r_keys, r_ch = self._read_internal_keys(right, self._read_page_header(right)[1])
            c_keys.append(p_keys[idx])
            c_ch.append(r_ch.pop(0))
            p_keys[idx] = r_keys.pop(0)
            self._write_internal_keys(child, c_keys, c_ch)
            self._write_internal_keys(right, r_keys, r_ch)
            self._note(f"kölcsönzés (belső): kulcsforgatás a jobb testvéren át (Page {right} -> Page {child})")
        self._write_internal_keys(parent_id, p_keys, p_children)

    def _merge(self, parent_id, li, c_type):
        """A parent li. és li+1. gyerekét vonja össze a bal oldaliba."""
        p_keys, p_children = self._read_internal_keys(parent_id, self._read_page_header(parent_id)[1])
        left, right = p_children[li], p_children[li + 1]
        if c_type == NODE_TYPE_LEAF:
            _, ln, _ = self._read_page_header(left)
            _, rn, rnext = self._read_page_header(right)
            merged = self._read_leaf_records(left, ln) + self._read_leaf_records(right, rn)
            self._write_leaf_records(left, merged, rnext)
        else:
            l_keys, l_ch = self._read_internal_keys(left, self._read_page_header(left)[1])
            r_keys, r_ch = self._read_internal_keys(right, self._read_page_header(right)[1])
            self._write_internal_keys(left, l_keys + [p_keys[li]] + r_keys, l_ch + r_ch)
        del p_keys[li]
        del p_children[li + 1]
        self._write_internal_keys(parent_id, p_keys, p_children)
        self._free_page(right)
        self._note(f"összevonás: Page {right} -> Page {left}, Page {right} felszabadítva")

    def _shrink_root(self):
        """Ha a gyökér belső node és 0 kulcsa maradt, az egyetlen gyereke lesz az új gyökér."""
        n_type, num_keys, _ = self._read_page_header(0)
        if n_type == NODE_TYPE_INTERNAL and num_keys == 0:
            _, children = self._read_internal_keys(0, 0)
            only_child = children[0]
            with open(self.filename, "rb+") as f:
                f.seek(self._get_page_offset(only_child))
                data = f.read(PAGE_SIZE)
                f.seek(0)
                f.write(data)
            self._free_page(only_child)
            self._note(f"a gyökér kiürült: Page {only_child} tartalma lett az új gyökér (Page 0), "
                       f"a fa magassága eggyel csökkent")



    def all_records_via_leaves(self):
        page_id = 0
        while True:
            n_type, num_keys, _ = self._read_page_header(page_id)
            if n_type == NODE_TYPE_LEAF:
                break
            page_id = self._read_internal_keys(page_id, num_keys)[1][0]
        out = []
        while page_id != -1:
            _, num_keys, nxt = self._read_page_header(page_id)
            out.extend(self._read_leaf_records(page_id, num_keys))
            page_id = nxt
        return out

    def check_invariants(self):
        leaf_depths = set()
        leaves_in_order = []

        def walk(pid, lo, hi, depth, is_root):
            n_type, num_keys, _ = self._read_page_header(pid)
            assert n_type in (NODE_TYPE_LEAF, NODE_TYPE_INTERNAL), f"Page {pid}: hibás típus"
            if n_type == NODE_TYPE_LEAF:
                recs = self._read_leaf_records(pid, num_keys)
                ks = [r[0] for r in recs]
                assert ks == sorted(ks), f"Page {pid}: rendezetlen levél"
                assert len(ks) <= MAX_LEAF_RECORDS
                if not is_root:
                    assert len(ks) >= MIN_LEAF_RECORDS, f"Page {pid}: alulcsordult levél"
                for k in ks:
                    assert (lo is None or k >= lo) and (hi is None or k < hi), f"Page {pid}: kulcs tartományon kívül"
                leaf_depths.add(depth)
                leaves_in_order.append(pid)
                return
            keys, children = self._read_internal_keys(pid, num_keys)
            assert keys == sorted(keys) and len(set(keys)) == len(keys)
            assert len(keys) <= MAX_INTERNAL_KEYS
            assert len(keys) >= (1 if is_root else MIN_INTERNAL_KEYS), f"Page {pid}: alulcsordult belső node"
            bounds = [lo] + keys + [hi]
            for j, c in enumerate(children):
                walk(c, bounds[j], bounds[j + 1], depth + 1, False)

        walk(0, None, None, 0, True)
        assert len(leaf_depths) <= 1,
        chain, pid = [], leaves_in_order[0]
        while pid != -1:
            chain.append(pid)
            pid = self._read_page_header(pid)[2]
        assert chain == leaves_in_order,

    def dump_file_structure(self):
        total_pages = os.path.getsize(self.filename) // PAGE_SIZE
        print(f"\n--- [ {os.path.basename(self.filename)} FÁJL STRUKTÚRA ({total_pages} LAP) ] ---")
        for p_id in range(total_pages):
            n_type, num_keys, next_p = self._read_page_header(p_id)
            if n_type == NODE_TYPE_INTERNAL:
                keys, children = self._read_internal_keys(p_id, num_keys)
                print(f"  Page {p_id} [BELSŐ NODE]: Kulcsok={keys} | Gyerek Lapok={children}")
            elif n_type == NODE_TYPE_LEAF:
                recs = self._read_leaf_records(p_id, num_keys)
                rec_ids = [r[0] for r in recs]
                next_str = f" -> Page {next_p}" if next_p != -1 else " -> NIL"
                print(f"  Page {p_id} [LEVÉL NODE] : Rekord ID-k={rec_ids} | Következő levél={next_str}")
            else:
                print(f"  Page {p_id} [SZABAD LAP] (újrahasznosítható)")



if __name__ == "__main__":
    INTERAKTIV = "-i" in sys.argv

    def tovabb():
        if INTERAKTIV:
            input("Tovább (Enter)!")

    DB_FILE = "data.bin"
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    teszt_adatok = [
        (1, "Hallgato_1_Miskolc"),
        (2, "Hallgato_2_Debrecen"),
        (3, "Hallgato_3_Gyor"),
        (6, "Hallgato_4_Pecs"),
        (5, "Hallgato_5_Szeged"),
        (4, "Hallgato_6_Budapest"),
        (7, "Hallgato_7_Sopron"),
        (8, "Hallgato_8_Pecs"),
        (9, "Hallgato_9_Szeged"),
        (10, "Hallgato_10_Budapest"),
        (11, "Hallgato_11_Sopron")
    ]

    db = DiskBPlusTreeVisualizer(DB_FILE)

    print("##################################################")
    print("#  BESZÚRÁSOK (órai kód)                          #")
    print("##################################################")
    for rec_id, name in teszt_adatok:
        db.insert(rec_id, name)
    db.dump_file_structure()
    tovabb()

    print("\n##################################################")
    print("#  1. FELADAT – KERESÉS                           #")
    print("##################################################")
    for k in (7, 1, 11, 42):
        db.search(k)
    tovabb()

    print("\nBónusz – tartományi keresés (BETWEEN 4 AND 9) a levéllánc segítségével:")
    eredmeny, lepes = db.range_search(4, 9)
    for r in eredmeny:
        print("   ", r)
    print(f"   ({lepes} lap beolvasása: lefelé a fában, majd végig a levélláncon)")
    tovabb()

    print("\n##################################################")
    print("#  2. FELADAT – TÖRLÉS                            #")
    print("##################################################")
    for k in (4, 5, 42, 1, 2, 3, 6, 7):
        print("\n==================================================")
        db.delete(k)
        db.dump_file_structure()
        db.check_invariants()
        tovabb()

    print("\nÚjrabeszúrás – a felszabadult lapokat újrahasznosítja:")
    for rec_id, name in [(1, "Uj_1"), (2, "Uj_2"), (3, "Uj_3"), (4, "Uj_4")]:
        db.insert(rec_id, name)
    db.dump_file_structure()
    db.check_invariants()
    db.search(3)
    print("\nÖsszes rekord a levélláncon:", db.all_records_via_leaves())
