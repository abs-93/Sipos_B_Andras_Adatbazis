"""Automatikus teszt a hash_program.py logikájához (ismert tesztvektorok alapján).
Futtatás: python teszt_hash_program.py"""
import hashlib
import os
import tempfile

from hash_program import (algoritmus_tippelese, egyezik, fajl_hash, szoveg_hash)

# Szabványos tesztvektorok (az "abc" szöveg hash-ei – FIPS 180 / RFC 1321)
VEKTOROK = {
    "MD5": "900150983cd24fb0d6963f7d28e17f72",
    "SHA-1": "a9993e364706816aba3e25717850c26c9cd0d89d",
    "SHA-256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    "SHA-512": "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a"
               "2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f",
}

ok = 0
for alg, vart in VEKTOROK.items():
    assert szoveg_hash("abc", alg) == vart, alg
    ok += 1
print(f"[OK] szöveg hash – {ok} algoritmus a szabványos 'abc' tesztvektorral")

# Fájl hash = hashlib referencia, kis darabmérettel is (a darabolás ne rontson el semmit)
with tempfile.NamedTemporaryFile(delete=False) as f:
    f.write(os.urandom(3_000_001))
    ut = f.name
adat = open(ut, "rb").read()
for alg, nev in (("MD5", "md5"), ("SHA-1", "sha1"), ("SHA-256", "sha256"), ("SHA-512", "sha512")):
    ref = hashlib.new(nev, adat).hexdigest()
    assert fajl_hash(ut, alg) == ref
    assert fajl_hash(ut, alg, chunk=4097) == ref
print("[OK] fájl hash (3 MB véletlen adat) = hashlib referencia, darabolt olvasással is")

# Folyamatjelző 100%-ra fut
lepesek = []
fajl_hash(ut, "SHA-256", chunk=1_000_000, folyamat=lepesek.append)
assert abs(lepesek[-1] - 1.0) < 1e-9
print(f"[OK] folyamatjelző: {len(lepesek)} lépés, utolsó = {lepesek[-1]:.0%}")

# Összehasonlítás: nagybetű, szóköz nem számít; 1 bájt módosítás -> nem egyezik
h = fajl_hash(ut, "SHA-256")
assert egyezik(h, "  " + h.upper()[:32] + " " + h.upper()[32:] + "\n")
with open(ut, "r+b") as f:
    f.seek(1_500_000)
    b = f.read(1)
    f.seek(1_500_000)
    f.write(bytes([b[0] ^ 1]))                # egyetlen BIT átfordítása
assert not egyezik(fajl_hash(ut, "SHA-256"), h)
print("[OK] ellenőrzés: egyezés felismerése; 1 bit módosítás után NEM EGYEZIK")

# Algoritmus felismerése a hash hosszából
assert [algoritmus_tippelese(v) for v in VEKTOROK.values()] == list(VEKTOROK)
print("[OK] algoritmus felismerése a hash hosszából (32/40/64/128 hexa karakter)")

# Üres fájl
with tempfile.NamedTemporaryFile(delete=False) as f:
    ures = f.name
assert fajl_hash(ures, "SHA-256") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
print("[OK] üres fájl SHA-256 = e3b0c442...b855 (a jegyzetben is ez a példa-hash!)")
os.remove(ut)
os.remove(ures)
print("\nMinden teszt sikeres.")
