"""
Adatbázis-kezelés 1 – 2. lecke, 1. feladat:
Készíts egy programot, amely bemutatja a fájlok hash-elését!

Követelmények és megvalósításuk:
  [x] fájl kiválasztása                       -> "Tallózás..." gomb (fájlválasztó ablak)
  [x] algoritmus választása                   -> legördülő lista: MD5, SHA-1, SHA-256, SHA-512
  [x] hash előállítása a kiválasztott fájlhoz -> "Hash számítása" gomb
  [x] megadott hash és fájl összehasonlítása  -> "Ellenőrzés" gomb: EGYEZIK / NEM EGYEZIK
  [+] szöveg hash-elése (mint a C# minta: string -> bájtok -> hash -> hexa string)
  [+] az összes algoritmus egyszerre, a hash hossza bitben
  [+] darabolt olvasás + folyamatjelző -> több GB-os fájl is mehet, a GUI nem fagy le
  [+] hash vágólapra másolása, kis-/nagybetű és szóközök figyelmen kívül hagyása

MD5: gyors, de ma már NEM biztonságos (ütközések állíthatók elő) – csak gyors
     ellenőrzésre jó. SHA-256: biztonságos, modern, ezt érdemes használni.

Futtatás:  python hash_program.py                  (grafikus felület, tkinter)
           python hash_program.py fajl [ALG] [várt_hash]   (parancssoros mód)
"""
import hashlib
import os
import sys
import threading

ALGORITMUSOK = {
    "MD5": "md5",
    "SHA-1": "sha1",
    "SHA-256": "sha256",
    "SHA-512": "sha512",
}


# =====================================================================
#  LOGIKA (GUI nélkül is használható és tesztelhető)
# =====================================================================
def fajl_hash(utvonal, algoritmus="SHA-256", chunk=1024 * 1024, folyamat=None):
    """A fájlt darabokban olvassa, így a memóriahasználat a fájlmérettől független."""
    h = hashlib.new(ALGORITMUSOK[algoritmus])
    meret = os.path.getsize(utvonal) or 1
    kesz = 0
    with open(utvonal, "rb") as f:
        while darab := f.read(chunk):
            h.update(darab)
            kesz += len(darab)
            if folyamat:
                folyamat(kesz / meret)
    return h.hexdigest()


def szoveg_hash(szoveg, algoritmus="SHA-256", kodolas="utf-8"):
    """C# minta megfelelője: Encoding.UTF8.GetBytes -> ComputeHash -> hexa string."""
    return hashlib.new(ALGORITMUSOK[algoritmus], szoveg.encode(kodolas)).hexdigest()


def normalizal(hash_szoveg):
    return "".join(hash_szoveg.split()).lower()


def egyezik(fajl_hash_ertek, megadott):
    return normalizal(fajl_hash_ertek) == normalizal(megadott)


def algoritmus_tippelese(hash_szoveg):
    """A hash hosszából kitalálja az algoritmust (hexa karakterek * 4 = bitek)."""
    hossz = len(normalizal(hash_szoveg))
    return {32: "MD5", 40: "SHA-1", 64: "SHA-256", 128: "SHA-512"}.get(hossz)


# =====================================================================
#  GRAFIKUS FELÜLET (tkinter)
# =====================================================================
def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("Fájl hash-elő – MD5 / SHA")
    root.geometry("780x520")
    root.minsize(700, 480)

    fajl_var = tk.StringVar()
    alg_var = tk.StringVar(value="SHA-256")
    eredmeny_var = tk.StringVar()
    vart_var = tk.StringVar()
    allapot_var = tk.StringVar(value="Válassz egy fájlt!")
    szoveg_var = tk.StringVar(value="Miskolci Egyetem")
    szoveg_eredmeny_var = tk.StringVar()

    pad = {"padx": 8, "pady": 4}

    # ---- 1. Fájl kiválasztása ----
    f1 = ttk.LabelFrame(root, text=" 1. Fájl kiválasztása ")
    f1.pack(fill="x", **pad)
    ttk.Entry(f1, textvariable=fajl_var).pack(side="left", fill="x", expand=True, padx=6, pady=6)

    def tallozas():
        ut = filedialog.askopenfilename(title="Fájl kiválasztása")
        if ut:
            fajl_var.set(ut)
            eredmeny_var.set("")
            allapot_var.set(f"Kiválasztva: {os.path.basename(ut)} ({os.path.getsize(ut):,} bájt)".replace(",", " "))

    ttk.Button(f1, text="Tallózás...", command=tallozas).pack(side="left", padx=6)

    # ---- 2. Algoritmus + számítás ----
    f2 = ttk.LabelFrame(root, text=" 2. Algoritmus és hash előállítása ")
    f2.pack(fill="x", **pad)
    sor = ttk.Frame(f2)
    sor.pack(fill="x", padx=6, pady=6)
    ttk.Label(sor, text="Algoritmus:").pack(side="left")
    ttk.Combobox(sor, textvariable=alg_var, values=list(ALGORITMUSOK), state="readonly",
                 width=10).pack(side="left", padx=6)
    gomb_szamit = ttk.Button(sor, text="Hash számítása")
    gomb_szamit.pack(side="left", padx=6)
    gomb_osszes = ttk.Button(sor, text="Mind a 4 algoritmus")
    gomb_osszes.pack(side="left", padx=6)
    progress = ttk.Progressbar(f2, mode="determinate", maximum=100)
    progress.pack(fill="x", padx=6)
    eredmeny_entry = ttk.Entry(f2, textvariable=eredmeny_var, state="readonly", font=("Consolas", 10))
    eredmeny_entry.pack(fill="x", padx=6, pady=6)

    def masol():
        root.clipboard_clear()
        root.clipboard_append(eredmeny_var.get())
        allapot_var.set("Hash a vágólapra másolva.")

    ttk.Button(f2, text="Másolás vágólapra", command=masol).pack(anchor="e", padx=6, pady=(0, 6))

    def ellenoriz_fajl():
        ut = fajl_var.get()
        if not ut or not os.path.isfile(ut):
            messagebox.showwarning("Hiba", "Előbb válassz ki egy létező fájlt!")
            return None
        return ut

    def hatterben(feladat, kesz):
        """Hosszú számítás külön szálon, hogy a felület ne fagyjon le."""
        gomb_szamit.state(["disabled"])
        gomb_osszes.state(["disabled"])

        def futtat():
            try:
                eredmeny = feladat()
                root.after(0, lambda: kesz(eredmeny))
            except OSError as e:
                root.after(0, lambda: messagebox.showerror("Hiba", str(e)))
            finally:
                root.after(0, lambda: (gomb_szamit.state(["!disabled"]), gomb_osszes.state(["!disabled"])))

        threading.Thread(target=futtat, daemon=True).start()

    def folyamat(arany):
        root.after(0, lambda: progress.configure(value=arany * 100))

    def szamit():
        ut = ellenoriz_fajl()
        if not ut:
            return
        alg = alg_var.get()
        allapot_var.set(f"{alg} számítása...")

        def kesz(h):
            eredmeny_var.set(h)
            allapot_var.set(f"{alg} kész ({len(h) * 4} bit, {len(h)} hexa karakter).")

        hatterben(lambda: fajl_hash(ut, alg, folyamat=folyamat), kesz)

    def osszes():
        ut = ellenoriz_fajl()
        if not ut:
            return

        def kesz(eredmenyek):
            szoveg = "\n".join(f"{a:<8} ({len(h) * 4:>3} bit): {h}" for a, h in eredmenyek.items())
            messagebox.showinfo(f"Hash értékek – {os.path.basename(ut)}", szoveg)
            eredmeny_var.set(eredmenyek[alg_var.get()])
            allapot_var.set("Mind a 4 algoritmus kész.")

        hatterben(lambda: {a: fajl_hash(ut, a) for a in ALGORITMUSOK}, kesz)

    gomb_szamit.configure(command=szamit)
    gomb_osszes.configure(command=osszes)

    # ---- 3. Összehasonlítás ----
    f3 = ttk.LabelFrame(root, text=" 3. Fájl ellenőrzése megadott hash alapján ")
    f3.pack(fill="x", **pad)
    sor3 = ttk.Frame(f3)
    sor3.pack(fill="x", padx=6, pady=6)
    ttk.Label(sor3, text="Várt hash:").pack(side="left")
    ttk.Entry(sor3, textvariable=vart_var, font=("Consolas", 10)).pack(side="left", fill="x", expand=True, padx=6)
    eredmeny_cimke = tk.Label(f3, text="", font=("Segoe UI", 12, "bold"))
    eredmeny_cimke.pack(pady=(0, 6))

    def ellenoriz():
        ut = ellenoriz_fajl()
        if not ut:
            return
        vart = vart_var.get()
        if not vart.strip():
            messagebox.showwarning("Hiba", "Add meg a várt hash értéket!")
            return
        tipp = algoritmus_tippelese(vart)
        if tipp and tipp != alg_var.get():
            alg_var.set(tipp)                       # a hossz alapján átállítjuk
        alg = alg_var.get()

        def kesz(h):
            eredmeny_var.set(h)
            if egyezik(h, vart):
                eredmeny_cimke.configure(text="✔ EGYEZIK – a fájl sértetlen", fg="#1a7f37")
            else:
                eredmeny_cimke.configure(text="✘ NEM EGYEZIK – a fájl módosult vagy hibás", fg="#c62828")
            allapot_var.set(f"Ellenőrzés kész ({alg}).")

        hatterben(lambda: fajl_hash(ut, alg, folyamat=folyamat), kesz)

    ttk.Button(sor3, text="Ellenőrzés", command=ellenoriz).pack(side="left")

    # ---- 4. Szöveg hash ----
    f4 = ttk.LabelFrame(root, text=" 4. Szöveg hash-elése (string -> UTF-8 bájtok -> hash) ")
    f4.pack(fill="x", **pad)
    sor4 = ttk.Frame(f4)
    sor4.pack(fill="x", padx=6, pady=6)
    ttk.Entry(sor4, textvariable=szoveg_var).pack(side="left", fill="x", expand=True)

    def szoveg_szamit(*_):
        szoveg_eredmeny_var.set(szoveg_hash(szoveg_var.get(), alg_var.get()))

    szoveg_var.trace_add("write", szoveg_szamit)
    alg_var.trace_add("write", szoveg_szamit)
    ttk.Entry(f4, textvariable=szoveg_eredmeny_var, state="readonly",
              font=("Consolas", 10)).pack(fill="x", padx=6, pady=(0, 6))
    szoveg_szamit()

    ttk.Label(root, textvariable=allapot_var, relief="sunken", anchor="w").pack(side="bottom", fill="x")

    # tesztelhetőség: a felület elemei kívülről is elérhetők
    root._hash_app = dict(fajl=fajl_var, alg=alg_var, vart=vart_var, szamit=szamit,
                          ellenoriz=ellenoriz, eredmeny=eredmeny_var, cimke=eredmeny_cimke,
                          allapot=allapot_var)
    return root


# =====================================================================
#  PARANCSSOROS MÓD
# =====================================================================
def cli(args):
    ut = args[0]
    alg = args[1].upper() if len(args) > 1 else "SHA-256"
    if alg not in ALGORITMUSOK:
        alg = {"SHA256": "SHA-256", "SHA1": "SHA-1", "SHA512": "SHA-512"}.get(alg, "SHA-256")
    h = fajl_hash(ut, alg)
    print(f"Fájl:       {ut} ({os.path.getsize(ut)} bájt)")
    print(f"{alg + ':':<11} {h}")
    if len(args) > 2:
        print("Ellenőrzés:", "EGYEZIK" if egyezik(h, args[2]) else "NEM EGYEZIK")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli(sys.argv[1:])
    else:
        gui().mainloop()
