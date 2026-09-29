import os
from storage_engine import StorageEngine


def cim(szoveg):
    print("\n" + "=" * 70)
    print(" " + szoveg)
    print("=" * 70)


def meret(fajl, rs):
    s = os.path.getsize(fajl)
    print(f"   Fájlméret: {s} bájt = {s // rs} rekordhely × {rs} bájt")


cim("1. FELADAT – adatok írása és visszaolvasása (record_size = 64)")
FAJL = "adatbazis.bin"
if os.path.exists(FAJL):
    os.remove(FAJL)
db = StorageEngine(FAJL, record_size=64)

db.write_record(0, "Miskolci Egyetem")
db.write_record(1, "Adatbáziskezelés")
db.write_record(2, "Oracle APEX")
db.write_record(3, "Negyedik adat")
db.write_record(4, "Ötödik adat")

print("read_record(1) ->", db.read_record(1))
print("read_record(4) ->", db.read_record(4))
print("read_record(99) ->", db.read_record(99), "(nem létező rekord)")
print("read_all_records():")
for r in db.read_all_records():
    print("  ", r)

cim("2. FELADAT – fájlszerkezet és méret változása")
print("a) 5 rekord (ID 0–4) után:")
meret(FAJL, 64)

db.write_record(10, "Tizedik hely")
print("b) write_record(10, ...) után – az 5–9. helyek ÜRESEN lefoglalódnak:")
meret(FAJL, 64)

db.write_record(2, "Oracle APEX – felülírva")
print("c) meglévő rekord (ID 2) felülírása után – a méret NEM változik:")
meret(FAJL, 64)

db.write_record(100, "100. hely")
print("d) write_record(100, ...) után – a fájl 'lyukas' lesz (sparse):")
meret(FAJL, 64)
print("   Érvényes rekordok száma:", len(db.read_all_records()),
      "– miközben a fájl", os.path.getsize(FAJL) // 64, "rekordhelyet foglal!")

print("\nHexa nézet az első 3 rekordról:")
db.hexdump(max_records=3)
print("\nMegfigyelés: minden rekord 8 bájt big-endian ID-val kezdődik (pl. 00 00 00 00 00 00 00 02),")
print("utána jön a név UTF-8 bájtjai (az 'á' = C3 A1, 'é' = C3 A9), majd 00 kitöltés a rekord végéig.")


cim("3. FELADAT – delete_record")
print("delete_record(3) ->", db.delete_record(3))
print("delete_record(3) ismét ->", db.delete_record(3), "(már nincs mit törölni)")
print("read_record(3) ->", db.read_record(3), "– csupa 0x00 (üres hely), a fájlméret változatlan:")
meret(FAJL, 64)

print("\ndelete_record(100) – az utolsó rekord törlésekor a fájl végét levágjuk (truncate):")
db.delete_record(100)
meret(FAJL, 64)

print("\nA törölt hely újrahasznosítható: write_record(3, 'Új negyedik')")
db.write_record(3, "Új negyedik")
for r in db.read_all_records():
    print("  ", r)


cim("4. FELADAT – RECORD_SIZE / RECORD_FORMAT változtatása")
adatok = [(0, "Miskolci Egyetem"), (1, "Adatbáziskezelés"), (2, "Oracle APEX"), (5, "Hatodik hely")]

print(f"{'record_size':>11} | {'formátum':>8} | {'fájlméret':>9} | hasznos bájt | kihasználtság")
print("-" * 66)
for rs in (32, 64, 128, 256):
    fn = f"meret_{rs}.bin"
    if os.path.exists(fn):
        os.remove(fn)
    e = StorageEngine(fn, record_size=rs)
    for i, n in adatok:
        e.write_record(i, n)
    s = os.path.getsize(fn)
    hasznos = sum(8 + min(len(n.encode()), rs - 8) for _, n in adatok)
    print(f"{rs:>11} | {e.record_format:>8} | {s:>9} | {hasznos:>12} | {hasznos / s * 100:6.1f} %")

print("\nRECORD_FORMAT = '>q120s' (record_size = 128) – hexa nézet:")
e128 = StorageEngine("meret_128.bin", record_size=128)
e128.hexdump(max_records=4)

print("\nRövid rekordméret (record_size = 16 -> '>q8s'): a hosszú nevek LEVÁGÓDNAK:")
if os.path.exists("meret_16.bin"):
    os.remove("meret_16.bin")
e16 = StorageEngine("meret_16.bin", record_size=16)
e16.write_record(0, "Miskolci Egyetem")
e16.write_record(1, "Adatbáziskezelés")
for r in e16.read_all_records():
    print("  ", r)

print("\nVESZÉLY: ugyanazt a fájlt MÁS rekordmérettel olvasva hibás adatot kapunk!")
print("(a 64 bájtos rekordokkal írt adatbazis.bin-t 128 bájtos motorral olvassuk)")
rossz = StorageEngine(FAJL, record_size=128)
for i in range(3):
    r = rossz.read_record(i)
    print(f"   id={r['id']}  name={r['name'].replace(chr(0), '·')!r}")
print("   (· = 0x00 bájt; két 64 bájtos rekord 'összeolvadt' egy 128 bájtos rekordba)")
print("Tanulság: a rekordformátumot a fájl fejlécében is tárolni kellene (metaadat)!")
