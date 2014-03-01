import sqlite3
con = sqlite3.connect("pplan.db")

con.executescript(
'''
CREATE TABLE mitbewohner(
  id INT,
  name TEXT NOT NULL,
  active BOOLEAN DEFAULT 1,
  birthday ISODATE NOT NULL,
  joining ISODATE,
  retirement ISODATE DEFAULT '2099-01-01',
  CHECK (date(joining) < date(retirement)),
  PRIMARY KEY(name)
);
CREATE TABLE aufgaben(
  name TEXT NOT NULL,
  PRIMARY KEY(NAME)
);
CREATE TABLE putzplan(
  start ISODATE,
  end ISODATE DEFAULT '2099-01-01',
  CHECK (date(start) < date(end))
);

CREATE TABLE aufgabenverteilung(
  putzplan_id INT,
  person_id TEXT,
  aufgabe_id TEXT,
  FOREIGN KEY(putzplan_id) REFERENCES putzplan(rowid),
  FOREIGN KEY(person_id) REFERENCES mitbewohner(name),
  FOREIGN KEY(aufgabe_id) REFERENCES aufgabe(name)
);
''')

#fill in some data - there are random:

con.executescript('''

INSERT INTO mitbewohner(name, active, birthday, joining) VALUES ("Christoph", 1, "1990-03-13", "2011-09-01");
INSERT INTO mitbewohner(name, active, birthday, joining) VALUES ("Stulli", 1, "1988-02-12", "2013-03-01");
INSERT INTO mitbewohner(name, active, birthday, joining) VALUES ("Johanna", 0, "1992-02-26", "2012-09-03");
INSERT INTO mitbewohner(name, active, birthday, joining) VALUES ("Schmiddler", 1, "1990-07-04", "2011-09-01");
INSERT INTO mitbewohner(name, active, birthday, joining) VALUES ("Christina", 1, "1994-04-12", "2013-03-01");


INSERT INTO aufgaben(name) VALUES("Saugen");
INSERT INTO aufgaben(name) VALUES("Wischen");
INSERT INTO aufgaben(name) VALUES("Kueche");
INSERT INTO aufgaben(name) VALUES("Ofen/Mikro");
INSERT INTO aufgaben(name) VALUES("Aufraeumen");
INSERT INTO aufgaben(name) VALUES("Toiletten");

''')


con.commit()
con.close()

