#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define SOR_MERET     256
#define NEV_MERET     56
#define VARAKOZAS_MP  5

typedef struct {
    long id;
    char nev[NEV_MERET];
} Rekord;

static void varakozas(int masodperc)
{
    time_t kezdet = time(NULL);
    while (difftime(time(NULL), kezdet) < (double)masodperc) {
    }
}

static long fajl_meret(const char *nev)
{
    long meret;
    FILE *f = fopen(nev, "rb");
    if (f == NULL) return -1L;
    fseek(f, 0L, SEEK_END);
    meret = ftell(f);
    fclose(f);
    return meret;
}

static int rekord_ir(const char *fajl, long id, const char *nev)
{
    Rekord r;
    FILE *f = fopen(fajl, "r+b");
    if (f == NULL) f = fopen(fajl, "w+b");
    if (f == NULL) return 0;

    memset(&r, 0, sizeof(r));
    r.id = id;
    strncpy(r.nev, nev, NEV_MERET - 1);

    fseek(f, id * (long)sizeof(Rekord), SEEK_SET);
    fwrite(&r, sizeof(Rekord), 1, f);
    fclose(f);
    return 1;
}

static int rekord_olvas(const char *fajl, long id, Rekord *ki)
{
    FILE *f = fopen(fajl, "rb");
    size_t db;
    if (f == NULL) return 0;
    if (fseek(f, id * (long)sizeof(Rekord), SEEK_SET) != 0) { fclose(f); return 0; }
    db = fread(ki, sizeof(Rekord), 1, f);
    fclose(f);
    return db == 1 && ki->nev[0] != '\0';
}

int main(void)
{
    FILE *f, *ki, *olvaso;
    char sor[SOR_MERET];
    const char *keresett = "uszas";
    int talalat = 0;
    long i, rekordszam;
    Rekord r;

    printf("=== 1) Szöveges fájl olvasása, fájlmutató léptetése ===\n");
    f = fopen("helsinki.txt", "r");
    if (f == NULL) {
        printf("HIBA: a helsinki.txt nem nyitható meg!\n");
        return EXIT_FAILURE;
    }

    fgets(sor, SOR_MERET, f);
    fgets(sor, SOR_MERET, f);
    printf("(Az első két sort átléptük, a fájlmutató most a %ld. bájton áll.)\n", ftell(f));
    while (fgets(sor, SOR_MERET, f) != NULL)
        printf("%s", sor);


    printf("\n=== 2) Lineáris keresés: \"%s\" ===\n", keresett);
    rewind(f);
    ki = fopen("talalatok.txt", "w");
    if (ki == NULL) { fclose(f); return EXIT_FAILURE; }

    while (fgets(sor, SOR_MERET, f) != NULL) {
        if (strstr(sor, keresett) != NULL) {
            printf("%s", sor);
            fputs(sor, ki);
            talalat++;
        }
    }
    fclose(f);
    printf("Találatok száma: %d\n", talalat);

    printf("\n=== 3) Perzisztencia és pufferelés ===\n");
    printf("A találatokat kiírtuk, de NEM zártuk le a fájlt (nincs fclose/fflush).\n");
    printf("A talalatok.txt mérete a lemezen most: %ld bájt\n", fajl_meret("talalatok.txt"));
    printf("Várakozás %d mp... (közben nyisd meg a talalatok.txt-t egy szerkesztőben: üres!)\n",
           VARAKOZAS_MP);
    fflush(stdout);
    varakozas(VARAKOZAS_MP);

    olvaso = fopen("talalatok.txt", "r");
    printf("Egy második olvasó ezt látja: \"%s\"\n",
           (olvaso != NULL && fgets(sor, SOR_MERET, olvaso) != NULL) ? "van tartalom" : "ÜRES");
    if (olvaso != NULL) fclose(olvaso);

    fflush(ki);
    printf("fflush() után a fájl mérete: %ld bájt\n", fajl_meret("talalatok.txt"));
    fclose(ki);

    olvaso = fopen("talalatok.txt", "r");
    printf("A lemezen tárolt találatok:\n");
    while (olvaso != NULL && fgets(sor, SOR_MERET, olvaso) != NULL)
        printf("  %s", sor);
    if (olvaso != NULL) fclose(olvaso);


    printf("\n=== 4) Bináris rekordok – fwrite / fseek / fread ===\n");
    remove("rekordok.bin");
    rekord_ir("rekordok.bin", 0, "Miskolci Egyetem");
    rekord_ir("rekordok.bin", 1, "Adatbaziskezeles");
    rekord_ir("rekordok.bin", 2, "Oracle APEX");
    rekord_ir("rekordok.bin", 5, "Otodik hely");
    printf("Rekordméret: %lu bájt, fájlméret: %ld bájt\n",
           (unsigned long)sizeof(Rekord), fajl_meret("rekordok.bin"));

    rekordszam = fajl_meret("rekordok.bin") / (long)sizeof(Rekord);
    for (i = 0; i < rekordszam; i++) {
        if (rekord_olvas("rekordok.bin", i, &r))
            printf("  [%ld] id=%ld nev=%s\n", i, r.id, r.nev);
        else
            printf("  [%ld] (üres hely)\n", i);
    }
    printf("Direkt elérés: 2. rekord -> ");
    if (rekord_olvas("rekordok.bin", 2, &r)) printf("%s\n", r.nev);

    {
        long futas = 0;
        FILE *sz = fopen("futasok.bin", "rb");
        if (sz != NULL) { fread(&futas, sizeof(long), 1, sz); fclose(sz); }
        futas++;
        sz = fopen("futasok.bin", "wb");
        if (sz != NULL) { fwrite(&futas, sizeof(long), 1, sz); fclose(sz); }
        printf("\nEz a program %ld. futása (futasok.bin – újraindításkor nő).\n", futas);
    }
    return EXIT_SUCCESS;
}
