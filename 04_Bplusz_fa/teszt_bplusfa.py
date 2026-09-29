import os
import random
from bplusfa import DiskBPlusTreeVisualizer

FILE = "teszt_data.bin"


def futtat(seed, muveletek=600, kulcster=200):
    rnd = random.Random(seed)
    if os.path.exists(FILE):
        os.remove(FILE)
    db = DiskBPlusTreeVisualizer(FILE)
    ref = {}
    max_steps = 0
    for _ in range(muveletek):
        k = rnd.randint(1, kulcster)
        if rnd.random() < 0.6:
            name = f"nev_{k}_{rnd.randint(0, 999)}"
            db.insert(k, name)
            ref[k] = name
        else:
            assert db.delete(k, verbose=False) == (k in ref), f"delete({k}) visszatérési értéke hibás"
            ref.pop(k, None)
        db.check_invariants()


        for q in rnd.sample(range(1, kulcster + 1), 10):
            rec, steps = db.search(q, verbose=False)
            max_steps = max(max_steps, steps)
            assert (rec[1] if rec else None) == ref.get(q), f"search({q}) hibás"
        assert db.all_records_via_leaves() == sorted(ref.items()), "levéllánc tartalma hibás"


    for k in list(ref):
        assert db.delete(k, verbose=False)
        db.check_invariants()
    assert db.all_records_via_leaves() == []
    pages = os.path.getsize(FILE) // 256
    os.remove(FILE)
    return max_steps, pages


if __name__ == "__main__":
    for seed in range(1, 11):
        steps, pages = futtat(seed)
        print(f"seed={seed:2d}: OK  (600 művelet, max. keresési lépésszám: {steps}, fájl: {pages} lap)")
    print("\nMinden teszt sikeres: a keresés és a törlés helyes, a B+fa szabályai mindig teljesülnek.")
