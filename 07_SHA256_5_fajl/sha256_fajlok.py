"""
Adatbázis-kezelés 1 – 2. lecke, GYAKORLATI FELADAT:
Határozd meg 5 általad tetszőlegesen kiválasztott fájl SHA256-hash-ét!

Az órai pythonsha256.py alapján, kiegészítve:
  - több fájl egyszerre (parancssori argumentumként, vagy ha nincs megadva,
    a mappa első 5 fájlja)
  - darabolt (chunk-os) olvasás -> nagy fájlokhoz is jó, és Python 3.11 alatt is fut
  - fájlméret kiírása, és a lavina-effektus bemutatása (1 bájt eltérés)

Futtatás:
  python sha256_fajlok.py fajl1 fajl2 fajl3 fajl4 fajl5
  python sha256_fajlok.py                (az aktuális mappa első 5 fájlja)

Ellenőrzés: Windows:  certutil -hashfile fajl.txt SHA256
            Linux:    sha256sum fajl.txt
            Online:   https://hu.piliapp.com/file/sha/
"""
import hashlib
import os
import sys


def get_file_sha256(file_path, chunk_size=64 * 1024):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    fajlok = sys.argv[1:]
    if not fajlok:
        fajlok = sorted(f for f in os.listdir(".") if os.path.isfile(f))[:5]

    print(f"{'Fájl':<28} {'Méret':>9}  SHA-256")
    print("-" * 106)
    for fajl in fajlok:
        try:
            print(f"{os.path.basename(fajl):<28} {os.path.getsize(fajl):>7} B  {get_file_sha256(fajl)}")
        except FileNotFoundError:
            print(f"{fajl:<28} [HIBA] A fájl nem található!")

    # Lavina-effektus: egyetlen karakter eltérés -> teljesen más hash
    print("\nLavina-effektus:")
    for s in ("Adatbázis-kezelés", "Adatbázis-kezelés!", "adatbázis-kezelés"):
        print(f"  {s!r:<22} -> {hashlib.sha256(s.encode('utf-8')).hexdigest()}")
