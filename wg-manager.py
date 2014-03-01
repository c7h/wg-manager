from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import sqlite3
from random import shuffle

import curses
import time

dbfile = "pplan.db"

#converter/adapter for ISOSTR DB-Type
def convert_isostr_datetime(isostr):
	return datetime.strptime(isostr, "%Y-%m-%d")

def adapt_isodate(date):
	'''take datetime-object and return isoformat-string YYYY-MM-DD'''
	return date.date().isoformat()


sqlite3.register_converter("ISODATE", convert_isostr_datetime)
sqlite3.register_adapter(datetime, adapt_isodate)



class Singleton(type):
	_instances = {}
	def __call__(cls, *args, **kwargs):
		if cls not in cls._instances:
			cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
		return cls._instances[cls]


class AufgabenDAO(object):
	__metaclass__ = Singleton
	def __init__(self):
		conn = sqlite3.connect(dbfile)
		self.c = conn.cursor()
		self.__conn = conn

	def getAufgaben(self):
		result = self.c.execute('SELECT name FROM aufgaben').fetchall()
		return map(lambda a: a[0], result)

	def __del__(self):
		self.__conn.close()


class Mitbewohner(object):
	def __init__(self, name, birth_date=datetime(1900, 1, 1), joining_date=None, retirement_date=None, isActive=True):
		self.name = name
		self.joining_date = joining_date
		self.retirement_date = retirement_date
		self.birthdate = birth_date
		self.isActive = isActive

	@property
	def alter(self):
		today = datetime.now()
		try: 
			birthday = self.birthdate.replace(year=today.year)
		except ValueError: # raised when birth date is February 29 and the current year is not a leap year
			birthday = self.birthdate.replace(year=today.year, day=self.birthdate.day - 1)
		if birthday > today:
			return today.year - self.birthdate.year - 1
		else:
			return today.year - self.birthdate.year
	

	
	def __repr__(self):
		return self.name

class MitbewohnerDAO(object):
	__metaclass__ = Singleton
	def __init__(self):
		conn = sqlite3.connect(dbfile, detect_types=sqlite3.PARSE_DECLTYPES)
		self.c = conn.cursor()
		self.__conn = conn

	def getMitbewohner(self):
		res = self.c.execute('SELECT name, active, birthday, joining, retirement FROM mitbewohner')
		mitbewohner = []
		for m in res:
			mitbew = Mitbewohner(name=m[0], isActive=m[1], birth_date=m[2], joining_date=m[3], retirement_date=m[4])	
			mitbewohner.append(mitbew)
		return mitbewohner

	def getMitbewohnerByID(self, id):
		res = self.c.excecute('''SELECT * name, active, birthday, joining, retirement FROM mitbewohner WHERE id=?''', (id))
		if len(res) <= 0:
			#nothing found
			return None
		else:
			m = res.fetchone()
			return  Mitbewohner(name=m[0], isActive=m[1], birth_date=m[2], joining_date=m[3], retirement_date=m[4])
	def getActiveMitbewohner(self):
		return filter(lambda m: m.isActive == True, self.getMitbewohner())	

	def __del__(self):
		self.__conn.close()

class Putzplan(object):

	def __init__(self, validSince, validTill, aufgabenverteilung_dict=dict()):
		self.__validTill = validTill
		self.__validSince = validSince
		self.aufgabenverteilung = aufgabenverteilung_dict	

	def getActivityDict(self):
		'''return dict of actual putzplan: STR Mitbewohner: STR Aufgabe'''
		return self.aufgabenverteilung

	@property
	def startDate(self):
		return self.__validSince

	@property
	def expiredDate(self):
		return self.__validTill

	def __repr__(self):
		return "Putzplan [%s bis %s]" % (self.__validSince.date().isoformat() , self.expiredDate.date().isoformat())


class PutzplanDAO(object):
	__metaclass__ = Singleton
	def __init__(self):
		conn = sqlite3.connect(dbfile, detect_types=sqlite3.PARSE_DECLTYPES)
		self.c = conn.cursor()
		self.__conn = conn


	@staticmethod
	def createRandomPutzplan(expires):
		aufgaben = AufgabenDAO().getAufgaben()
		mitbewohner = MitbewohnerDAO().getActiveMitbewohner()
		shuffle(mitbewohner)
		shuffle(aufgaben)
		aufgabenverteilung = dict (zip(mitbewohner, aufgaben))

		start_date = datetime.now().date()
		end_date = start_date + timedelta(days=expires)
		pplan = Putzplan(start_date, end_date, aufgabenverteilung)
		return pplan


	def getActual(self):
		#@TODO: mal richtig machen....
		res = self.c.execute('''SELECT start, end, rowid FROM putzplan WHERE date('now') < date(end)''').fetchone()
		if not res:
			#not found
			return None
		else:
			pplan_id = res[2]
			aufgaben_res = self.c.execute('''SELECT aufgabe_id, name, birthday, joining, retirement, active from aufgabenverteilung JOIN mitbewohner ON aufgabenverteilung.person_id = mitbewohner.name WHERE aufgabenverteilung.putzplan_id = ?''', (pplan_id,)).fetchall()
			aufgabenverteilung = dict()
			for aufgabe_id, name, birthday, joining, retirement, active in aufgaben_res:
				aufgabenverteilung[Mitbewohner(name, birthday, joining, retirement, active)] = aufgabe_id
			return Putzplan(validSince=res[0], validTill=res[1], aufgabenverteilung_dict=aufgabenverteilung)

	def save(self, putzplan):
		aufgaben = putzplan.aufgabenverteilung #dict format-- Mitbewohner mitbew : str aufgabe

		self.c.execute('''INSERT INTO putzplan(start, end) VALUES (?, ?)''', (putzplan.startDate, putzplan.expiredDate))
		putzplan_id = self.c.execute('''SELECT rowid FROM putzplan WHERE start=? AND end=?''', (putzplan.startDate, putzplan.expiredDate)).fetchone()[0]

		for person, aufgabe in aufgaben.iteritems():
			table_row = person.name, aufgabe, putzplan_id #@TODO: change person.name to person.id
			#table_row_set.append(table_row)
			self.c.execute('''INSERT INTO aufgabenverteilung(person_id, aufgabe_id, putzplan_id) VALUES (?, ?, ?)''', table_row)
		self.__conn.commit()

	def __del__(self):
		self.__conn.close()

class Application(object):
	def __init__(self):
		self.putzplanDAO = PutzplanDAO()
		self.mitbewohnerDAO = MitbewohnerDAO()

	def newRandomPutzplan(self, expires=7):
		putzplanDAO = PutzplanDAO()
		neuer_plan = putzplanDAO.createRandomPutzplan(expires)
		putzplanDAO.save(neuer_plan)


	def getActualPutzplan(self):
		actualPutzplan = self.putzplanDAO.getActual()
		if not actualPutzplan:
			self.newRandomPutzplan()
			actualPutzplan = self.putzplanDAO.getActual()	
		return actualPutzplan
		
	
	def birthdays(self):
		'''return generator: (mitbewohner, birthday_timedelta)'''
		#@TODO: this is ugly!
		now = datetime.now()
		mitbewohner = self.mitbewohnerDAO.getMitbewohner()
		mitbewohner.sort(key=lambda m: m.birthdate, reverse=True)
		for person in mitbewohner:
			next_birthday = datetime(now.year, person.birthdate.month, person.birthdate.day)
			if next_birthday < now:
				next_birthday + relativedelta(years=1)
			birthday_timedelta = now - next_birthday
			yield (person, birthday_timedelta.days)
			

class CLIGUI(object):
	
	def __init__(self):
		self.app = Application()

	def printPutzplan(self):
		print "Aktueller Plan"
		actualPutzplan = self.app.getActualPutzplan()
		print actualPutzplan
		print
		activitys = actualPutzplan.getActivityDict()
		for person, aufgabe in activitys.iteritems():
			print "%12s => %s" % (person.name, aufgabe)
			
	def printUpcommingBirthdays(self):
		for person, td in self.app.birthdays():
			if td < 0:
				#person hat dieses jahr noch geburtstag
				print "%10s wird in %3i Tagen %i [%s]" % (person.name, td * -1, person.alter, person.birthdate.date())
			elif td == 0:
				#person hat heute geburtstag
				print "*** %s hat HEUTE Geburtstag ***" % person.name
			elif td > 10:
				#person hatte die innerhalb der letzen 10 tage geburtstag
				print ""
			
				
			#print "%12s: %s t[%+i]" % (person.name, person.birthdate.date(), td)





class CursesGUI(object):
	def __init__(self):
		self.scr = curses.initscr()
		curses.noecho()
		curses.cbreak()
		
		#color
		curses.start_color()
		curses.use_default_colors()
		curses.init_pair(1, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
		
		self.scr.keypad(1)
		self.height, self.width = self.scr.getmaxyx()
		
		self.app = Application()
			
				
	def displayWelcomeScreen(self, str="Putzplan v0.1 beta im Schleifbrauehaus"):		
		self._cleanscreen()
		x_mitte = self.height / 2
		y_mitte = self.width / 2 - len(str) / 2
		self.scr.addstr(x_mitte, y_mitte, str)
		self.scr.refresh()
		return self

	
	def displayPutzplan(self):
		self._cleanscreen()
		actualPutzplan = self.app.getActualPutzplan()
		header = actualPutzplan.__repr__()
		activitys = actualPutzplan.getActivityDict()
		
		self.scr.addstr(0, 2, header, curses.color_pair(1))
		line_counter = 2
		for person, aufgabe in activitys.iteritems():
			self.scr.addstr(line_counter, 2, person.name)
			self.scr.addstr(line_counter, self.width / 2 + 2, aufgabe)
			line_counter = line_counter + 1
		self.scr.refresh()
		return self
	
	def displayBirthdays(self):
		self._cleanscreen()
		self.scr.addstr(0, 2, "Geburtstage in diesem Jahr", curses.color_pair(1))
		
		
		linecounter = 1
		for person, td in self.app.birthdays():
			if td < 0:
				#person hat dieses jahr noch geburtstag
				str = "%s wird in %3i Tagen %i" % (person.name, td * -1, person.alter )
			elif td == 0:
				#person hat heute geburtstag
				str = "*** %s hat HEUTE Geburtstag ***" % person.name
				
			elif td < 10:
				#person hatte die innerhalb der letzen 10 tage geburtstag
				str = "%s ist vor %i Tagen %i geworden" % (person.name, td, person.alter)
			else:
				continue
			self.scr.addstr(linecounter, 2, str)
			bday_str = person.birthdate.date().isoformat()
			self.scr.addstr(linecounter, self.width-len(bday_str)-3, "["+bday_str+"]")
			linecounter += 1
		
		
		self.scr.refresh()		
		return self

		
	
	#helper - initiate clean screen
	def _cleanscreen(self):
		self.scr.clear()
		self.scr.border(0)
		
		
	
	def wait(self, seconds):
		time.sleep(seconds)
		return self
	
	def __del__(self):
		##go back to normal
		curses.nocbreak()
		curses.echo()
		curses.endwin()



if __name__ == "__main__":
	#app = CLIGUI()
	#app.printPutzplan()
	#print
	#app.printUpcommingBirthdays()
	
	app = CursesGUI()
	app.displayWelcomeScreen()
	while True:
		app.displayBirthdays().wait(10).displayPutzplan().wait(10)

	
