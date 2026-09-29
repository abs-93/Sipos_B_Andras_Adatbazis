import multiprocessing
import os
import struct
import threading
import time

PAGE_SIZE = 512
RECORD_SIZE = 64
RECORD_FORMAT = ">q56s"


class RWLock:


    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._readers = 0
        self._writer = False
        self._writers_waiting = 0

    def acquire_read(self):
        with self._cond:
            while self._writer or self._writers_waiting:
                self._cond.wait()
            self._readers += 1

    def release_read(self):
        with self._cond:
            self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    def acquire_write(self):
        with self._cond:
            self._writers_waiting += 1
            while self._writer or self._readers:
                self._cond.wait()
            self._writers_waiting -= 1
            self._writer = True

    def release_write(self):
        with self._cond:
            self._writer = False
            self._cond.notify_all()


    class _Ctx:
        def __init__(self, enter, leave):
            self._enter, self._leave = enter, leave

        def __enter__(self):
            self._enter()

        def __exit__(self, *exc):
            self._leave()

    def read_locked(self):
        return RWLock._Ctx(self.acquire_read, self.release_read)

    def write_locked(self):
        return RWLock._Ctx(self.acquire_write, self.release_write)



class ProcessFileLock:
    """Kizárólagos zár egy <adatfájl>.lock segédfájlon. Más programok /
    folyamatok ugyanígy zárolva nem tudnak egyszerre írni."""

    def __init__(self, path):
        self.path = path + ".lock"

    def __enter__(self):
        self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT)
        if os.name == "nt":
            import msvcrt
            os.lseek(self._fd, 0, os.SEEK_SET)
            while True:
                try:
                    msvcrt.locking(self._fd, msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    pass
        else:
            import fcntl
            fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if os.name == "nt":
            import msvcrt
            os.lseek(self._fd, 0, os.SEEK_SET)
            msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)


class StorageEngine:
    _locks = {}
    _locks_guard = threading.Lock()

    def __init__(self, filename="data.bin", process_safe=False, io_delay=0.0):
        self.filename = os.path.abspath(filename)
        self.process_safe = process_safe
        self.io_delay = io_delay
        with StorageEngine._locks_guard:
            self.lock = StorageEngine._locks.setdefault(self.filename, RWLock())
        with self.lock.write_locked():
            if not os.path.exists(self.filename):
                with open(self.filename, "wb"):
                    pass


    def _raw_write(self, record_id, name):
        encoded = name.encode("utf-8")[:56].ljust(56, b"\x00")
        data = struct.pack(RECORD_FORMAT, record_id, encoded)
        with open(self.filename, "rb+") as f:
            f.seek(record_id * RECORD_SIZE)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if self.io_delay:
            time.sleep(self.io_delay)

    def _raw_read(self, record_id):
        offset = record_id * RECORD_SIZE
        if os.path.getsize(self.filename) < offset + RECORD_SIZE:
            return None
        with open(self.filename, "rb") as f:
            f.seek(offset)
            data = f.read(RECORD_SIZE)
        if self.io_delay:
            time.sleep(self.io_delay)
        rec_id, raw = struct.unpack(RECORD_FORMAT, data)
        name = raw.rstrip(b"\x00").decode("utf-8", errors="ignore")
        if not name:
            return None
        return {"id": rec_id, "name": name}

    def _plock(self):
        return ProcessFileLock(self.filename) if self.process_safe else _NoLock()

    @staticmethod
    def _check_id(record_id):
        if not isinstance(record_id, int) or record_id < 0:
            raise ValueError(f"Érvénytelen rekord ID: {record_id!r}")


    def write_record(self, record_id: int, name: str):
        self._check_id(record_id)
        with self.lock.write_locked(), self._plock():
            self._raw_write(record_id, name)

    def read_record(self, record_id: int):
        self._check_id(record_id)
        with self.lock.read_locked():
            return self._raw_read(record_id)

    def update_record(self, record_id: int, fuggveny):
        self._check_id(record_id)
        with self.lock.write_locked(), self._plock():
            regi = self._raw_read(record_id)
            uj = fuggveny(regi["name"] if regi else None)
            self._raw_write(record_id, uj)
            return uj

    def delete_record(self, record_id: int):
        self._check_id(record_id)
        with self.lock.write_locked(), self._plock():
            if self._raw_read(record_id) is None:
                return False
            with open(self.filename, "rb+") as f:
                f.seek(record_id * RECORD_SIZE)
                f.write(b"\x00" * RECORD_SIZE)
                f.flush()
                os.fsync(f.fileno())
            return True

    def read_all(self):
        with self.lock.read_locked():
            n = os.path.getsize(self.filename) // RECORD_SIZE
            return [r for r in (self._raw_read(i) for i in range(n)) if r]


class _NoLock:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


def cim(s):
    print("\n" + "=" * 72 + "\n " + s + "\n" + "=" * 72)


def friss(fajl):
    for f in (fajl, fajl + ".lock"):
        if os.path.exists(f):
            os.remove(f)


def teszt_1_iro_olvaso():
    cim("1) 6 író + 6 olvasó szál egyszerre – sérül-e rekord?")
    fajl = "teszt1.bin"
    friss(fajl)
    db = StorageEngine(fajl)
    hibak, olvasasok = [], [0]
    szamlalo_zar = threading.Lock()
    kesz = threading.Event()

    def iro(sz):
        for i in range(40):
            rid = sz * 100 + i
            db.write_record(rid, f"Adat_{rid}_" + "x" * (rid % 30))

    def olvaso():
        while not kesz.is_set():
            for rid in range(0, 600, 7):
                r = db.read_record(rid)
                if r is not None:
                    if r["id"] != rid or r["name"] != f"Adat_{rid}_" + "x" * (rid % 30):
                        hibak.append(r)
                    with szamlalo_zar:
                        olvasasok[0] += 1

    irok = [threading.Thread(target=iro, args=(s,), name=f"Iro-{s}") for s in range(6)]
    olvasok = [threading.Thread(target=olvaso, name=f"Olvaso-{k}") for k in range(6)]
    for t in olvasok + irok:
        t.start()
    for t in irok:
        t.join()
    kesz.set()
    for t in olvasok:
        t.join()

    osszes = db.read_all()
    print(f"Kiírt rekordok: {len(osszes)} (elvárt: 240)")
    print(f"Párhuzamos sikeres olvasások: {olvasasok[0]}, sérült rekord: {len(hibak)}")
    print("EREDMÉNY:", "OK" if len(osszes) == 240 and not hibak else "HIBA")


def teszt_2_lost_update():
    cim("2) LOST UPDATE: 8 szál × 50 növelés ugyanazon a számlálón")
    fajl = "teszt2.bin"

    friss(fajl)
    db = StorageEngine(fajl)
    db.write_record(0, "0")

    def naiv():
        for _ in range(50):
            ertek = int(db.read_record(0)["name"])
            time.sleep(0.0005)
            db.write_record(0, str(ertek + 1))

    sz = [threading.Thread(target=naiv) for _ in range(8)]
    [t.start() for t in sz]
    [t.join() for t in sz]
    print(f"a) Naiv olvas + ír:         végérték = {db.read_record(0)['name']:>4}  (elvárt: 400)  <- módosítások elvesztek!")


    friss(fajl)
    db = StorageEngine(fajl)
    db.write_record(0, "0")

    def atomi():
        for _ in range(50):
            db.update_record(0, lambda regi: str(int(regi) + 1))

    sz = [threading.Thread(target=atomi) for _ in range(8)]
    [t.start() for t in sz]
    [t.join() for t in sz]
    v = db.read_record(0)["name"]
    print(f"b) Atomi update_record():   végérték = {v:>4}  (elvárt: 400)  -> {'OK' if v == '400' else 'HIBA'}")


def teszt_3_parhuzamos_olvasas():
    cim("3) Párhuzamos olvasás: RLock (órai kód) vs. RWLock (javított)")
    fajl = "teszt3.bin"
    friss(fajl)
    db = StorageEngine(fajl, io_delay=0.05)
    for i in range(8):
        db.write_record(i, f"rekord_{i}")


    rlock = threading.RLock()

    def olvas_rlock(i):
        with rlock:
            db._raw_read(i)

    def olvas_rw(i):
        db.read_record(i)

    for nev, fv in (("RLock  (egyszerre 1 olvasó)", olvas_rlock), ("RWLock (sok olvasó egyszerre)", olvas_rw)):
        sz = [threading.Thread(target=fv, args=(i,)) for i in range(8)]
        t0 = time.perf_counter()
        [t.start() for t in sz]
        [t.join() for t in sz]
        print(f"   {nev}: 8 olvasás ideje = {(time.perf_counter() - t0) * 1000:6.0f} ms")
    print("   -> az RWLock-kal az olvasások átfedik egymást, ~8× gyorsabb.")


def _folyamat_munkas(fajl, db_szam):
    db = StorageEngine(fajl, process_safe=True)
    for _ in range(db_szam):
        db.update_record(0, lambda regi: str(int(regi) + 1))


def teszt_4_tobb_folyamat():
    cim("4) Több FOLYAMAT (külön programpéldány) – OS szintű fájlzár")
    fajl = "teszt4.bin"
    friss(fajl)
    StorageEngine(fajl, process_safe=True).write_record(0, "0")
    procs = [multiprocessing.Process(target=_folyamat_munkas, args=(fajl, 100)) for _ in range(4)]
    t0 = time.perf_counter()
    [p.start() for p in procs]
    [p.join() for p in procs]
    v = StorageEngine(fajl).read_record(0)["name"]
    print(f"4 folyamat × 100 atomi növelés: végérték = {v} (elvárt: 400) -> {'OK' if v == '400' else 'HIBA'}"
          f"  [{(time.perf_counter() - t0):.2f} s]")


def teszt_5_orai_forgatokonyv():
    cim("5) Az órai forgatókönyv determinisztikusan (2 író, 3 olvasó)")
    fajl = "adatbazis.bin"
    friss(fajl)
    db = StorageEngine(fajl)
    irasok_kesz = {0: threading.Event(), 10: threading.Event()}
    print_zar = threading.Lock()

    def log(msg):
        with print_zar:
            print(msg)

    def worker_write(start_id):
        for i in range(3):
            rid = start_id + i
            db.write_record(rid, f"Adat_{rid}_thread_{threading.current_thread().name}")
            log(f"[SZÁL - {threading.current_thread().name}] ÍRÁS: ID={rid}")
        irasok_kesz[start_id].set()

    def worker_read(target_id, varj_erre):
        irasok_kesz[varj_erre].wait()
        r = db.read_record(target_id)
        log(f"  --> [SZÁL - {threading.current_thread().name}] OLVASÁS: {r}")

    sz = [threading.Thread(target=worker_write, args=(0,), name="Iro-1"),
          threading.Thread(target=worker_write, args=(10,), name="Iro-2"),
          threading.Thread(target=worker_read, args=(1, 0), name="Olvaso-1"),
          threading.Thread(target=worker_read, args=(11, 10), name="Olvaso-2"),
          threading.Thread(target=worker_read, args=(5, 0), name="Olvaso-3")]
    [t.start() for t in sz]
    [t.join() for t in sz]
    print("Az ID=5 egy 'lyuk' a fájlban -> javítva None-t ad (az órai kód {'id': 0, 'name': ''}-t).")
    print("Fájlméret:", os.path.getsize(fajl), "bájt =", os.path.getsize(fajl) // RECORD_SIZE, "rekordhely")


if __name__ == "__main__":
    teszt_1_iro_olvaso()
    teszt_2_lost_update()
    teszt_3_parhuzamos_olvasas()
    teszt_4_tobb_folyamat()
    teszt_5_orai_forgatokonyv()
    for f in ("teszt1.bin", "teszt2.bin", "teszt3.bin", "teszt4.bin"):
        friss(f)
