import os
import re
import struct
import sys
import zlib

DB_FILE = "adatbazis.mdb"
MAGIC = b"MINIDB01"
TYPES = {"INT": 1, "REAL": 2, "TEXT": 3}
TYPE_NAMES = {v: k for k, v in TYPES.items()}


class DBError(Exception):
    pass



class Table:
    def __init__(self, name, columns):
        self.name = name
        self.columns = columns
        self.rows = []

    @property
    def col_names(self):
        return [c[0] for c in self.columns]

    def col_index(self, col):
        for i, c in enumerate(self.columns):
            if c[0].lower() == col.lower():
                return i
        raise DBError(f"A '{self.name}' táblában nincs '{col}' oszlop!")

    def pk_index(self):
        for i, c in enumerate(self.columns):
            if c[2]:
                return i
        return None

    def convert(self, idx, value):
        """Érték konvertálása az oszlop típusára."""
        if value is None:
            if self.columns[idx][2]:
                raise DBError(f"A PRIMARY KEY oszlop ({self.columns[idx][0]}) nem lehet NULL!")
            return None
        typ = self.columns[idx][1]
        try:
            if typ == "INT":
                if isinstance(value, float) and not value.is_integer():
                    raise ValueError
                return int(value)
            if typ == "REAL":
                return float(value)
            return str(value)
        except (ValueError, TypeError):
            raise DBError(f"Típushiba: '{value}' nem {typ} ({self.columns[idx][0]} oszlop)")

    def check_pk(self, row, ignore_row=None):
        pk = self.pk_index()
        if pk is None:
            return
        for r in self.rows:
            if r is not ignore_row and r[pk] == row[pk]:
                raise DBError(f"PRIMARY KEY ütközés: {self.columns[pk][0]} = {row[pk]} már létezik!")


class Database:
    def __init__(self, filename=DB_FILE):
        self.filename = filename
        self.tables = {}
        if os.path.exists(filename):
            self.load()

    def get(self, name):
        t = self.tables.get(name.lower())
        if t is None:
            raise DBError(f"A '{name}' tábla nem létezik!")
        return t


    @staticmethod
    def _pack_str(s):
        b = s.encode("utf-8")
        return struct.pack(">I", len(b)) + b

    def save(self):
        out = bytearray(MAGIC)
        out += struct.pack(">H", len(self.tables))
        for t in self.tables.values():
            out += self._pack_str(t.name)
            out += struct.pack(">H", len(t.columns))
            for name, typ, pk in t.columns:
                out += self._pack_str(name)
                out += struct.pack(">BB", TYPES[typ], 1 if pk else 0)
            out += struct.pack(">I", len(t.rows))
            for row in t.rows:
                for (_, typ, _), v in zip(t.columns, row):
                    if v is None:
                        out += b"\x00"
                        continue
                    out += b"\x01"
                    if typ == "INT":
                        out += struct.pack(">q", v)
                    elif typ == "REAL":
                        out += struct.pack(">d", v)
                    else:
                        out += self._pack_str(v)
        out += struct.pack(">I", zlib.crc32(out) & 0xFFFFFFFF)

        tmp = self.filename + ".tmp"
        with open(tmp, "wb") as f:
            f.write(out)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.filename)
        return len(out)

    def load(self):
        with open(self.filename, "rb") as f:
            data = f.read()
        if data[:8] != MAGIC:
            raise DBError("Ismeretlen fájlformátum!")
        body, crc = data[:-4], struct.unpack(">I", data[-4:])[0]
        if zlib.crc32(body) & 0xFFFFFFFF != crc:
            raise DBError("A fájl sérült (CRC32 eltérés)!")

        pos = 8

        def take(fmt):
            nonlocal pos
            vals = struct.unpack_from(fmt, body, pos)
            pos += struct.calcsize(fmt)
            return vals if len(vals) > 1 else vals[0]

        def take_str():
            nonlocal pos
            n = take(">I")
            s = body[pos:pos + n].decode("utf-8")
            pos += n
            return s

        tables = {}
        for _ in range(take(">H")):
            name = take_str()
            cols = []
            for _ in range(take(">H")):
                cname = take_str()
                typ, pk = take(">BB")
                cols.append((cname, TYPE_NAMES[typ], bool(pk)))
            t = Table(name, cols)
            for _ in range(take(">I")):
                row = []
                for _, typ, _ in cols:
                    if take(">B") == 0:
                        row.append(None)
                    elif typ == "INT":
                        row.append(take(">q"))
                    elif typ == "REAL":
                        row.append(take(">d"))
                    else:
                        row.append(take_str())
                t.rows.append(row)
            tables[name.lower()] = t
        self.tables = tables



TOKEN_RE = re.compile(r"""
    \s*(?:
      (?P<str>'(?:[^']|'')*')              |
      (?P<num>-?\d+(?:\.\d+)?)            |
      (?P<op><=|>=|<>|!=|=|<|>)           |
      (?P<punct>[(),*;])                  |
      (?P<id>[A-Za-z_áéíóöőúüűÁÉÍÓÖŐÚÜŰ][\wáéíóöőúüűÁÉÍÓÖŐÚÜŰ]*)
    )""", re.VERBOSE)

KEYWORDS = {"SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "CREATE", "TABLE", "DROP",
            "UPDATE", "SET", "DELETE", "ORDER", "BY", "ASC", "DESC", "LIMIT", "AND", "OR",
            "NOT", "NULL", "IS", "LIKE", "PRIMARY", "KEY", "SHOW", "TABLES", "DESCRIBE",
            "COUNT", "SAVE", "LOAD", "HELP"}


def tokenize(sql):
    tokens, pos = [], 0
    sql = sql.strip()
    while pos < len(sql):
        m = TOKEN_RE.match(sql, pos)
        if not m or m.end() == pos:
            raise DBError(f"Értelmezhetetlen karakter itt: '{sql[pos:pos + 10]}'")
        pos = m.end()
        kind = m.lastgroup
        val = m.group(kind)
        if kind == "str":
            tokens.append(("STR", val[1:-1].replace("''", "'")))
        elif kind == "num":
            tokens.append(("NUM", float(val) if "." in val else int(val)))
        elif kind == "id":
            tokens.append(("KW", val.upper()) if val.upper() in KEYWORDS else ("ID", val))
        elif kind == "op":
            tokens.append(("OP", val))
        else:
            tokens.append(("SYM", val))
    while tokens and tokens[-1] == ("SYM", ";"):
        tokens.pop()
    return tokens


class Parser:
    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else (None, None)

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def accept(self, kind, val=None):
        tok = self.peek()
        if tok[0] == kind and (val is None or tok[1] == val):
            self.i += 1
            return True
        return False

    def expect(self, kind, val=None):
        tok = self.next()
        if tok[0] != kind or (val is not None and tok[1] != val):
            raise DBError(f"Szintaxishiba: '{val or kind}' kellene, de '{tok[1]}' jött.")
        return tok[1]

    def ident(self):
        tok = self.next()
        if tok[0] != "ID":
            raise DBError(f"Szintaxishiba: azonosító kellene, de '{tok[1]}' jött.")
        return tok[1]

    def end(self):
        if self.i != len(self.t):
            raise DBError(f"Szintaxishiba: felesleges rész a parancs végén: '{self.peek()[1]}'")

    def value(self):
        tok = self.next()
        if tok[0] in ("STR", "NUM"):
            return tok[1]
        if tok == ("KW", "NULL"):
            return None
        raise DBError(f"Érték kellene, de '{tok[1]}' jött.")

    def ident_list(self):
        out = [self.ident()]
        while self.accept("SYM", ","):
            out.append(self.ident())
        return out


    def condition(self):
        left = self.and_expr()
        while self.accept("KW", "OR"):
            left = ("OR", left, self.and_expr())
        return left

    def and_expr(self):
        left = self.atom()
        while self.accept("KW", "AND"):
            left = ("AND", left, self.atom())
        return left

    def atom(self):
        if self.accept("KW", "NOT"):
            return ("NOT", self.atom())
        if self.accept("SYM", "("):
            c = self.condition()
            self.expect("SYM", ")")
            return c
        col = self.ident()
        if self.accept("KW", "IS"):
            neg = self.accept("KW", "NOT")
            self.expect("KW", "NULL")
            return ("ISNOTNULL" if neg else "ISNULL", col)
        if self.accept("KW", "LIKE"):
            return ("LIKE", col, self.value())
        op = self.expect("OP")
        return ("CMP", op, col, self.value())


def eval_cond(cond, table, row):
    if cond is None:
        return True
    kind = cond[0]
    if kind == "AND":
        return eval_cond(cond[1], table, row) and eval_cond(cond[2], table, row)
    if kind == "OR":
        return eval_cond(cond[1], table, row) or eval_cond(cond[2], table, row)
    if kind == "NOT":
        return not eval_cond(cond[1], table, row)
    if kind in ("ISNULL", "ISNOTNULL"):
        v = row[table.col_index(cond[1])]
        return (v is None) == (kind == "ISNULL")
    if kind == "LIKE":
        v = row[table.col_index(cond[1])]
        if v is None:
            return False
        pattern = "^" + re.escape(str(cond[2])).replace("%", ".*").replace("_", ".") + "$"
        return re.match(pattern, str(v), re.IGNORECASE | re.DOTALL) is not None

    _, op, col, val = cond
    idx = table.col_index(col)
    v = row[idx]
    if v is None or val is None:
        return False
    val = table.convert(idx, val)
    return {"=": v == val, "!=": v != val, "<>": v != val, "<": v < val,
            ">": v > val, "<=": v <= val, ">=": v >= val}[op]



def print_table(headers, rows):
    def fmt(v):
        if v is None:
            return "NULL"
        if isinstance(v, float):
            return f"{v:g}"
        return str(v)

    str_rows = [[fmt(v) for v in r] for r in rows]
    widths = [max([len(h)] + [len(r[i]) for r in str_rows]) for i, h in enumerate(headers)]
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    print(sep)
    print("| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |")
    print(sep)
    for r in str_rows:
        print("| " + " | ".join(c.ljust(w) for c, w in zip(r, widths)) + " |")
    print(sep)
    print(f"({len(rows)} sor)")


HELP = """Parancsok:
  CREATE TABLE t (oszlop INT|REAL|TEXT [PRIMARY KEY], ...)
  DROP TABLE t                 SHOW TABLES              DESCRIBE t
  INSERT INTO t [(o1, o2)] VALUES (...), (...)
  SELECT * | o1, o2 | COUNT(*) FROM t [WHERE ...] [ORDER BY o [ASC|DESC]] [LIMIT n]
  UPDATE t SET o1 = érték, ... [WHERE ...]
  DELETE FROM t [WHERE ...]
  SAVE  /  LOAD  /  HELP  /  EXIT
  WHERE: = != <> < > <= >= LIKE 'A%'  IS [NOT] NULL  AND OR NOT ( )"""


def execute(db, sql):
    """Egy SQL parancs végrehajtása. Visszaadja, hogy módosult-e az adatbázis."""
    tokens = tokenize(sql)
    if not tokens:
        return False
    p = Parser(tokens)
    cmd = p.next()

    if cmd == ("KW", "HELP"):
        print(HELP)
        return False

    if cmd == ("KW", "SAVE"):
        p.end()
        print(f"Elmentve: {db.filename} ({db.save()} bájt)")
        return False

    if cmd == ("KW", "LOAD"):
        p.end()
        db.load()
        print(f"Betöltve: {db.filename} ({len(db.tables)} tábla)")
        return False

    if cmd == ("KW", "SHOW"):
        p.expect("KW", "TABLES")
        p.end()
        print_table(["tábla", "oszlopok", "sorok"],
                    [[t.name, len(t.columns), len(t.rows)] for t in db.tables.values()])
        return False

    if cmd == ("KW", "DESCRIBE"):
        t = db.get(p.ident())
        p.end()
        print_table(["oszlop", "típus", "kulcs"],
                    [[c[0], c[1], "PRIMARY KEY" if c[2] else ""] for c in t.columns])
        return False

    if cmd == ("KW", "CREATE"):
        p.expect("KW", "TABLE")
        name = p.ident()
        if name.lower() in db.tables:
            raise DBError(f"A '{name}' tábla már létezik!")
        p.expect("SYM", "(")
        cols = []
        while True:
            cname = p.ident()
            typ = p.ident().upper()
            if typ not in TYPES:
                raise DBError(f"Ismeretlen típus: {typ} (INT, REAL, TEXT használható)")
            pk = False
            if p.accept("KW", "PRIMARY"):
                p.expect("KW", "KEY")
                pk = True
            if cname.lower() in (c[0].lower() for c in cols):
                raise DBError(f"Ismétlődő oszlopnév: {cname}")
            cols.append((cname, typ, pk))
            if not p.accept("SYM", ","):
                break
        p.expect("SYM", ")")
        p.end()
        if sum(c[2] for c in cols) > 1:
            raise DBError("Legfeljebb egy PRIMARY KEY oszlop lehet!")
        db.tables[name.lower()] = Table(name, cols)
        print(f"A '{name}' tábla létrejött ({len(cols)} oszlop).")
        return True

    if cmd == ("KW", "DROP"):
        p.expect("KW", "TABLE")
        name = p.ident()
        p.end()
        db.get(name)
        del db.tables[name.lower()]
        print(f"A '{name}' tábla törölve.")
        return True

    if cmd == ("KW", "INSERT"):
        p.expect("KW", "INTO")
        t = db.get(p.ident())
        cols = t.col_names
        if p.accept("SYM", "("):
            cols = p.ident_list()
            p.expect("SYM", ")")
        p.expect("KW", "VALUES")
        new_rows = []
        while True:
            p.expect("SYM", "(")
            vals = [p.value()]
            while p.accept("SYM", ","):
                vals.append(p.value())
            p.expect("SYM", ")")
            if len(vals) != len(cols):
                raise DBError("Az oszlopok és az értékek száma nem egyezik!")
            row = [None] * len(t.columns)
            for c, v in zip(cols, vals):
                idx = t.col_index(c)
                row[idx] = t.convert(idx, v)
            pk = t.pk_index()
            if pk is not None and row[pk] is None:
                raise DBError(f"A PRIMARY KEY ({t.columns[pk][0]}) megadása kötelező!")
            t.check_pk(row)
            for nr in new_rows:
                if pk is not None and nr[pk] == row[pk]:
                    raise DBError(f"PRIMARY KEY ütközés: {row[pk]}")
            new_rows.append(row)
            if not p.accept("SYM", ","):
                break
        p.end()
        t.rows.extend(new_rows)
        print(f"{len(new_rows)} sor beszúrva a '{t.name}' táblába.")
        return True

    if cmd == ("KW", "SELECT"):
        count = False
        if p.accept("KW", "COUNT"):
            p.expect("SYM", "(")
            p.expect("SYM", "*")
            p.expect("SYM", ")")
            count = True
            cols = None
        elif p.accept("SYM", "*"):
            cols = None
        else:
            cols = p.ident_list()
        p.expect("KW", "FROM")
        t = db.get(p.ident())
        cond = p.condition() if p.accept("KW", "WHERE") else None
        order = None
        if p.accept("KW", "ORDER"):
            p.expect("KW", "BY")
            ocol = t.col_index(p.ident())
            desc = p.accept("KW", "DESC")
            if not desc:
                p.accept("KW", "ASC")
            order = (ocol, desc)
        limit = None
        if p.accept("KW", "LIMIT"):
            limit = p.expect("NUM")
        p.end()

        rows = [r for r in t.rows if eval_cond(cond, t, r)]
        if count:
            print_table(["COUNT(*)"], [[len(rows)]])
            return False
        if order:
            idx, desc = order
            rows.sort(key=lambda r: (r[idx] is None, r[idx] if r[idx] is not None else 0), reverse=False)
            if desc:
                nonnull = [r for r in rows if r[idx] is not None][::-1]
                rows = nonnull + [r for r in rows if r[idx] is None]
        if limit is not None:
            rows = rows[:int(limit)]
        idxs = list(range(len(t.columns))) if cols is None else [t.col_index(c) for c in cols]
        print_table([t.columns[i][0] for i in idxs], [[r[i] for i in idxs] for r in rows])
        return False

    if cmd == ("KW", "UPDATE"):
        t = db.get(p.ident())
        p.expect("KW", "SET")
        sets = []
        while True:
            c = t.col_index(p.ident())
            p.expect("OP", "=")
            sets.append((c, t.convert(c, p.value())))
            if not p.accept("SYM", ","):
                break
        cond = p.condition() if p.accept("KW", "WHERE") else None
        p.end()
        targets = [r for r in t.rows if eval_cond(cond, t, r)]
        pk = t.pk_index()
        new_versions = []
        for r in targets:
            nr = list(r)
            for c, v in sets:
                nr[c] = v
            new_versions.append(nr)
        if pk is not None and any(c == pk for c, _ in sets):
            untouched = [r[pk] for r in t.rows if not any(r is x for x in targets)]
            new_keys = [nr[pk] for nr in new_versions]
            if len(set(new_keys)) != len(new_keys) or set(new_keys) & set(untouched):
                raise DBError("PRIMARY KEY ütközés a módosítás után!")
        for r, nr in zip(targets, new_versions):
            r[:] = nr
        print(f"{len(targets)} sor módosítva.")
        return bool(targets)

    if cmd == ("KW", "DELETE"):
        p.expect("KW", "FROM")
        t = db.get(p.ident())
        cond = p.condition() if p.accept("KW", "WHERE") else None
        p.end()
        before = len(t.rows)
        t.rows = [r for r in t.rows if not eval_cond(cond, t, r)]
        print(f"{before - len(t.rows)} sor törölve.")
        return before != len(t.rows)

    raise DBError("Ismeretlen vagy hibás szintaxisú parancs! (HELP)")


def run(db, sql, echo=False):
    if echo:
        print(f"SQL> {sql}")
    try:
        if execute(db, sql):
            db.save()
    except DBError as e:
        print(f"Hiba: {e}")
    except Exception as e:
        print(f"Váratlan hiba: {e}")


def split_statements(text):
    """Parancsfájl feldarabolása ';' mentén (idézőjelen belül nem vág), -- megjegyzések kihagyásával."""
    stmts, cur, in_str = [], [], False
    for line in text.splitlines():
        if not in_str and line.strip().startswith("--"):
            continue
        for ch in line + "\n":
            if ch == "'":
                in_str = not in_str
            if ch == ";" and not in_str:
                s = "".join(cur).strip()
                if s:
                    stmts.append(s)
                cur = []
            else:
                cur.append(ch)
    s = "".join(cur).strip()
    if s:
        stmts.append(s)
    return stmts


def main():
    db = Database(DB_FILE)
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            for stmt in split_statements(f.read()):
                run(db, " ".join(stmt.split()), echo=True)
                print()
        return

    print("Egyszerű SQL adatbázis – több tábla, bináris mentés (" + DB_FILE + ")")
    print("Írd be: HELP a parancsokhoz, EXIT a kilépéshez.\n")
    while True:
        try:
            line = input("SQL> ")
        except EOFError:
            break
        if line.strip().lower().rstrip(";") in ("exit", "quit"):
            break
        if line.strip():
            run(db, line)


if __name__ == "__main__":
    main()
