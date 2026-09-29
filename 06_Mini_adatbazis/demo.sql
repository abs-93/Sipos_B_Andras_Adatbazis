-- Bemutató parancsfájl a bővített mini adatbázishoz
-- Futtatás: python mini_db.py demo.sql

CREATE TABLE users (id INT PRIMARY KEY, nev TEXT, varos TEXT, kor INT);
CREATE TABLE targyak (kod TEXT PRIMARY KEY, nev TEXT, kredit INT);
CREATE TABLE jegyek (user_id INT, targy_kod TEXT, jegy INT, atlag_suly REAL);
SHOW TABLES;
DESCRIBE users;

INSERT INTO users (id, nev, varos, kor) VALUES (1, 'Nagy Anna', 'Miskolc', 21), (2, 'Kovács Béla', 'Debrecen', 23), (3, 'Kis Pista', 'Miskolc', 20);
INSERT INTO users VALUES (4, 'O''Brien, Kate; vendég', 'Budapest', 25);
INSERT INTO users (id, nev) VALUES (5, 'Tóth Éva');
INSERT INTO targyak VALUES ('ADB1', 'Adatbázis-kezelés 1', 5), ('PRG1', 'Programozás 1', 6);
INSERT INTO jegyek VALUES (1, 'ADB1', 5, 1.0), (2, 'ADB1', 3, 1.0), (3, 'ADB1', 4, 1.0), (1, 'PRG1', 4, 1.5);

SELECT * FROM users;
SELECT nev, varos FROM users WHERE varos = 'Miskolc' ORDER BY nev;
SELECT * FROM users WHERE kor >= 21 AND (varos = 'Miskolc' OR varos = 'Budapest');
SELECT * FROM users WHERE nev LIKE 'K%';
SELECT id, nev FROM users WHERE varos IS NULL;
SELECT * FROM users ORDER BY kor DESC LIMIT 3;
SELECT COUNT(*) FROM jegyek WHERE targy_kod = 'ADB1';

-- Hibakezelés
INSERT INTO users VALUES (1, 'Duplikált', 'X', 1);
INSERT INTO users (id, nev, kor) VALUES (6, 'Hibás kor', 'húsz');
SELECT * FROM nincsilyen;
SELECT fizetes FROM users;

-- Módosítás és törlés
UPDATE users SET varos = 'Eger', kor = 30 WHERE id = 5;
UPDATE jegyek SET jegy = 4 WHERE user_id = 2 AND targy_kod = 'ADB1';
DELETE FROM users WHERE id = 3;
SELECT * FROM users;
SELECT * FROM jegyek;

DROP TABLE targyak;
SHOW TABLES;
