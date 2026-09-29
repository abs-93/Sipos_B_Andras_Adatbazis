using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace BinarisFajlDemo
{
    class StorageEngine
    {
        public const int RECORD_SIZE = 64;
        public const int NAME_SIZE = RECORD_SIZE - 8;
        private readonly string _fileName;

        public StorageEngine(string fileName)
        {
            _fileName = fileName;
            if (!File.Exists(_fileName))
                File.Create(_fileName).Dispose();
        }

        public void WriteRecord(long id, string name)
        {
            byte[] record = new byte[RECORD_SIZE];
            BinaryPrimitives.WriteInt64BigEndian(record.AsSpan(0, 8), id);
            byte[] nameBytes = Encoding.UTF8.GetBytes(name);
            Array.Copy(nameBytes, 0, record, 8, Math.Min(nameBytes.Length, NAME_SIZE));

            using var fs = new FileStream(_fileName, FileMode.Open, FileAccess.Write);
            fs.Seek(id * RECORD_SIZE, SeekOrigin.Begin);
            fs.Write(record, 0, RECORD_SIZE);
            fs.Flush(true);
        }

        public (long Id, string Name)? ReadRecord(long id)
        {
            long offset = id * RECORD_SIZE;
            var info = new FileInfo(_fileName);
            if (info.Length < offset + RECORD_SIZE) return null;

            byte[] record = new byte[RECORD_SIZE];
            using var fs = new FileStream(_fileName, FileMode.Open, FileAccess.Read);
            fs.Seek(offset, SeekOrigin.Begin);
            fs.ReadExactly(record, 0, RECORD_SIZE);

            long recId = BinaryPrimitives.ReadInt64BigEndian(record.AsSpan(0, 8));
            string name = Encoding.UTF8.GetString(record, 8, NAME_SIZE).TrimEnd('\0');
            if (name.Length == 0) return null;
            return (recId, name);
        }

        public void DeleteRecord(long id)
        {
            long offset = id * RECORD_SIZE;
            if (new FileInfo(_fileName).Length < offset + RECORD_SIZE) return;
            using var fs = new FileStream(_fileName, FileMode.Open, FileAccess.Write);
            fs.Seek(offset, SeekOrigin.Begin);
            fs.Write(new byte[RECORD_SIZE], 0, RECORD_SIZE);
        }

        public List<(long Id, string Name)> ReadAll()
        {
            var list = new List<(long, string)>();
            long count = new FileInfo(_fileName).Length / RECORD_SIZE;
            for (long i = 0; i < count; i++)
            {
                var r = ReadRecord(i);
                if (r != null) list.Add(r.Value);
            }
            return list;
        }
    }

    class Program
    {
        static void Cim(string s)
        {
            Console.WriteLine();
            Console.WriteLine(new string('=', 64));
            Console.WriteLine(" " + s);
            Console.WriteLine(new string('=', 64));
        }

        static void HexDump(string file, int maxBytes = 256)
        {
            byte[] data = File.ReadAllBytes(file);
            int n = Math.Min(data.Length, maxBytes);
            for (int i = 0; i < n; i += 16)
            {
                var hex = new StringBuilder();
                var asc = new StringBuilder();
                for (int j = 0; j < 16; j++)
                {
                    if (i + j < n)
                    {
                        byte b = data[i + j];
                        hex.Append(b.ToString("X2")).Append(' ');
                        asc.Append(b >= 32 && b < 127 ? (char)b : '.');
                    }
                    else hex.Append("   ");
                }
                Console.WriteLine($"{i:X8}  {hex} |{asc}|");
            }
            if (data.Length > n) Console.WriteLine($"... (összesen {data.Length} bájt)");
        }

        static void Main()
        {
            Console.OutputEncoding = Encoding.UTF8;

            Cim("1) BinaryWriter / BinaryReader – primitív típusok");
            const string primFile = "primitivek.bin";
            using (var bw = new BinaryWriter(File.Open(primFile, FileMode.Create), Encoding.UTF8))
            {
                bw.Write(42);
                bw.Write(3.14159);
                bw.Write(true);
                bw.Write('Á');
                bw.Write("Miskolci Egyetem");
                bw.Write(new byte[] { 0x00, 0xFF, 0x10 });

            Console.WriteLine($"Kiírva: {primFile} ({new FileInfo(primFile).Length} bájt)");

            using (var br = new BinaryReader(File.OpenRead(primFile), Encoding.UTF8))
            {
                int i = br.ReadInt32();
                double d = br.ReadDouble();
                bool b = br.ReadBoolean();
                char c = br.ReadChar();
                string s = br.ReadString();
                byte[] raw = br.ReadBytes(3);
                Console.WriteLine($"Visszaolvasva: int={i}, double={d}, bool={b}, char={c}, string=\"{s}\", bytes={BitConverter.ToString(raw)}");
            }
            HexDump(primFile);

 
            Cim("2) Szöveges vs. bináris tárolás mérete");
            int[] szamok = { 7, 123456789, -2000000000, 65535, 1000000 };
            File.WriteAllText("szamok.txt", string.Join("\n", szamok));
            using (var bw = new BinaryWriter(File.Open("szamok.bin", FileMode.Create)))
                foreach (int x in szamok) bw.Write(x);
            Console.WriteLine($"szamok.txt : {new FileInfo("szamok.txt").Length,3} bájt (karakterenként + sorvégjelek)");
            Console.WriteLine($"szamok.bin : {new FileInfo("szamok.bin").Length,3} bájt (5 × 4 bájt, fix méret)");
            Console.WriteLine("A bináris fájlban a 3. szám közvetlenül elérhető: offset = 2 * 4 = 8");
            using (var br = new BinaryReader(File.OpenRead("szamok.bin")))
            {
                br.BaseStream.Seek(2 * sizeof(int), SeekOrigin.Begin);
                Console.WriteLine($"Seek(8) után olvasott érték: {br.ReadInt32()}");
            }


            Cim("3) Fix méretű rekordok – StorageEngine (direkt elérés)");
            const string dbFile = "adatbazis_cs.bin";
            if (File.Exists(dbFile)) File.Delete(dbFile);
            var db = new StorageEngine(dbFile);
            db.WriteRecord(0, "Miskolci Egyetem");
            db.WriteRecord(1, "Adatbáziskezelés");
            db.WriteRecord(2, "Oracle APEX");
            db.WriteRecord(5, "Ötödik hely – a 3. és 4. üres marad");
            Console.WriteLine($"Fájlméret 4 rekord után: {new FileInfo(dbFile).Length} bájt (6 × 64, mert a 3–4. hely is lefoglalódik)");
            foreach (var r in db.ReadAll()) Console.WriteLine($"  {r}");

            Console.WriteLine("\nRekord módosítása (ID=2) és törlése (ID=1):");
            db.WriteRecord(2, "Oracle APEX (módosítva)");
            db.DeleteRecord(1);
            foreach (var r in db.ReadAll()) Console.WriteLine($"  {r}");
            Console.WriteLine($"ReadRecord(1) → {(db.ReadRecord(1) == null ? "null (törölve)" : "van")}");


            Cim("4) Hexa dump – adatbazis_cs.bin első 3 rekordja");
            HexDump(dbFile, 3 * StorageEngine.RECORD_SIZE);
            Console.WriteLine("Megfigyelés: az első 8 bájt az ID big-endian formában (00 .. 00 02),");
            Console.WriteLine("utána a név UTF-8 bájtjai, majd 00-k a rekord végéig. A törölt 1. rekord csupa 00.");


            Cim("5) Perzisztencia – futásszámláló");
            const string counterFile = "futasszamlalo.bin";
            int futas = 0;
            if (File.Exists(counterFile))
                using (var br = new BinaryReader(File.OpenRead(counterFile)))
                    futas = br.ReadInt32();
            futas++;
            using (var bw = new BinaryWriter(File.Open(counterFile, FileMode.Create)))
            {
                bw.Write(futas);
                bw.Write(DateTime.Now.ToBinary());
            }
            Console.WriteLine($"Ez a program {futas}. futása. (Indítsd el újra – a szám nő, mert a fájlban tárolódik.)");
        }
    }
}
