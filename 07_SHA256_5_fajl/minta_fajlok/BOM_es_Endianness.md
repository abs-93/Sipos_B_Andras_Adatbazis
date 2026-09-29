# Feladat: Nézz utána a következő fogalmaknak! – BOM / without BOM, Big-Endian / Little-Endian

## 1. BOM (Byte Order Mark) – „BOM-mal” és „BOM nélkül” (without BOM)

**Mi az?** A BOM egy speciális Unicode karakter (**U+FEFF**, „zero width no-break space”), amelyet egy szöveges fájl **legelejére** írhatnak. Nem jelenik meg a szövegben, a feladata az, hogy jelezze az olvasó programnak:

1. **milyen Unicode kódolású** a fájl (UTF-8, UTF-16, UTF-32),
2. több bájtos kódolásnál (UTF-16/32) **milyen a bájtsorrend** (big- vagy little-endian) – innen a neve.

| Kódolás   | BOM bájtjai (hexa) | Megjegyzés |
|-----------|--------------------|------------|
| UTF-8     | `EF BB BF`         | UTF-8-ban nincs bájtsorrend-probléma, itt csak „aláírás” |
| UTF-16 LE | `FF FE`            | Windows (pl. Jegyzettömb „Unicode” mentése) |
| UTF-16 BE | `FE FF`            | |
| UTF-32 LE | `FF FE 00 00`      | |
| UTF-32 BE | `00 00 FE FF`      | |

Ha egy UTF-8 BOM-ot (`EF BB BF`) Windows-1252/1250 kódolásként jelenítünk meg, az `ï»¿` karaktereket látjuk a fájl elején – ez tipikus „karattyolás”.

**UTF-8 BOM-mal vs. BOM nélkül (UTF-8 without BOM)**

- **BOM-mal:** a fájl `EF BB BF`-fel kezdődik. Előny: a program biztosan felismeri, hogy UTF-8 (pl. régebbi Excel csak így nyitja meg helyesen az ékezetes CSV-t). A Windows-os eszközök (Jegyzettömb régebbi verziói, PowerShell 5, Visual Studio) gyakran így mentenek.
- **BOM nélkül:** a fájl rögtön a tartalommal kezdődik. Ez az **ajánlott és elterjedtebb** forma (Unicode szabvány, Linux, web, Python, Git, JSON – a JSON szabvány kifejezetten tiltja a BOM-ot).
- **Tipikus hibák BOM miatt:**
  - CSV első oszlopneve `"﻿id"` lesz `"id"` helyett, így a program nem találja az oszlopot;
  - PHP-nál „headers already sent” hiba, shell szkriptnél a `#!/bin/bash` sor nem működik;
  - két fájl összefűzésekor BOM kerül a szöveg közepére.
- **Kezelés:** Pythonban `encoding="utf-8-sig"` olvasáskor eltávolítja, íráskor hozzáadja a BOM-ot; C#-ban `new UTF8Encoding(false)` = BOM nélkül, `Encoding.UTF8` = BOM-mal (`File.WriteAllText` alapból BOM nélkül ír).

## 2. Big-Endian és Little-Endian (bájtsorrend)

Ha egy szám több bájtot foglal (pl. egy 32 bites egész 4 bájtot), meg kell állapodni, hogy a memóriában / fájlban **milyen sorrendben** követik egymást a bájtok.

Példa: a `0x12345678` szám (= 305 419 896) tárolása 4 bájton:

| Bájtsorrend | Cím: +0 | +1 | +2 | +3 | Jellemző |
|-------------|------|----|----|----|----------|
| **Big-Endian** (BE) | `12` | `34` | `56` | `78` | a **legnagyobb** helyiértékű bájt van elöl – „ahogy olvassuk” |
| **Little-Endian** (LE) | `78` | `56` | `34` | `12` | a **legkisebb** helyiértékű bájt van elöl |

- **Little-endian:** Intel/AMD x86-x64 processzorok, ARM (alapértelmezésben) – vagyis szinte minden PC és telefon. A C# `BinaryWriter`, a C `fwrite` egy `int`-tel a gép natív sorrendjében, tehát little-endian módon ír.
- **Big-endian:** hálózati protokollok („network byte order”, TCP/IP fejlécek), Java `DataOutputStream`, sok fájlformátum (PNG, JPEG fejlécek), régebbi Motorola/PowerPC/SPARC processzorok.
- Az elnevezés a *Gulliver utazásaiból* ered: a lilliputiak azon vitatkoztak, hogy a tojást a nagyobb (big end) vagy a kisebb (little end) végén kell feltörni.

**Miért fontos az adatbázis-kezelésben?** Bináris fájlnál a bájtsorrend a fájlformátum része. Ha az egyik program big-endian módon ír, a másik little-endian módon olvas, **hibás számokat** kapunk: a `0x12345678` helyett `0x78563412`-t (2 018 915 346). Ezért:

- az órai `StorageEngine` a `struct` formátumban **`>`** jellel (`">q56s"`) rögzíti a **big-endian** sorrendet – ezért látszik a hexa editorban az ID = 2 így: `00 00 00 00 00 00 00 02`; `<` jelentené a little-endiant;
- a B+fa fejlécében a `next_page_id = -1` big-endian 32 biten `FF FF FF FF` (szövegszerkesztőben `ÿÿÿÿ`);
- a C# példában (`01_CSharp_binaris_fajl`) a `BinaryWriter` little-endian módon ír (`2A 00 00 00` = 42), míg a rekordoknál `BinaryPrimitives.WriteInt64BigEndian` kell, hogy a Python programmal kompatibilis legyen;
- UTF-16/UTF-32 szövegnél a BOM mondja meg, hogy BE vagy LE a fájl.

A `bom_endian_demo.py` mindkét témát futtatható példákkal mutatja be (kimenete: `kimenet.txt`).
