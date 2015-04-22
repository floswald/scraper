from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, ElementNotVisibleException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from codecs import open


#http://stackoverflow.com/questions/989872/how-do-i-draw-out-specific-data-from-an-opened-url-in-python-using-urllib2/989920#989920



def launchScraper():

	#get a driver
	driver = startDriver()
	# out dict
	o = {}

	# each iteration new html page
	for b in banks:
		o[b] = {}
		for d in dates:
			o[b][d] = bank_date(b,d,driver)
	return o


def startDriver():
	""" start firefox as a driver and
	navigate to the correct search form"""

	driver = webdriver.Firefox()
	driver.get("https://www.clarkcountycourts.us/Anonymous/default.aspx")

	# click on district courts link
	driver.find_element_by_xpath("/html/body/table/tbody/tr[2]/td/table/tbody/tr[1]/td[2]/a[2][@class='ssSearchHyperlink']").click()
	return driver

def resetDriver(driver):
	""" bring browser back to search page
	after """




def bank_date(bank,date,driver):
	# go to drop down

	try:
		downelt = WebDriverWait(driver,10).until(EC.presence_of_element_located((By.XPATH,"//select[@id='SearchBy']")))
		ddown = Select(downelt)
	except ElementNotVisibleException:
		print "waited for 10 seconds to load search page. quitting driver."
		driver.quit()

	# select "Party"
	ddown.select_by_visible_text("Party")

	# click on radio button "Business"
	driver.find_element_by_xpath("//input[@id='PartyBusinessOption']").click()

	# fill in name of bank we are looking for
	driver.find_element_by_xpath("//input[@id='LastName']").send_keys(bank)

	# could specify dates here:
	driver.find_element_by_xpath("//input[@id='DateFiledOnAfter']").send_keys(date[0])
	driver.find_element_by_xpath("//input[@id='DateFiledOnBefore']").send_keys(date[1])

	# submit the search
	driver.find_element_by_xpath("//input[@id='SearchSubmit']").click()

	print "currently getting data of %s between %s and %s" % (bank, date[0], date[1])

	# get results

	# look only at those cases
	cases = parseCaseList(driver.page_source,"Breach of Contract")	# return a dict with keys case numbers

	# out dict
	d = {}

	# loop over all Breach of Contract cases
	for case in cases.keys():
		print "trying case %s" % case
		try:
			driver.find_element_by_link_text(case).click()    #click on the required link to access a single case
			d[case] = parseSingleCase(driver)	# get individual case data
		except NoSuchElementException:
			print "could not open link for case %s" % case
			pass
		except AttributeError:
			print "could not parse case %s" % case
			pass


	# return to previous page in browser before exiting
	driver.back()

	return d


def parseCaseList(src,term):
	soup = BeautifulSoup(src)
	# Breach of Contract cases
	# BoCcases = list()
	BoCcases = {}
	# get the results table
	tab = soup.find_all("table")[5:]   # look in index 5 onwards
	rows = tab[0].findAll('tr')
	for  rowv in rows[3:]:
		cols = rowv.findAll('td')
		# print "case: %s, type: %s" % (cols[0].text,cols[4].text)
		if  term in cols[4].text:
			BoCcases[cols[0].text] = rowv	# offset by 4 to account for how we started to count here.
			# BoCcases[rowi+4] = rowv	# offset by 4 to account for how we started to count here.
	# these are the indices in the results table that we have to get the data for
	# caseids = [BoCcases[i][0] for i in range(0,len(BoCcases))]
	print "    searching for %s turns up %d cases" % (term,len(rows[3:]))
	return BoCcases


def parseSingleCase(driver):

	soup = BeautifulSoup(driver.page_source)

	d = {}

	# get URL of this case. useless as far as I can see.
	d["URL"] = driver.current_url.encode('utf-8')

	print "parsing URL %s" % d["URL"]

	# get all table headers	of that class:
	h = soup.find_all(class_="ssTableHeaderLabel")

	# ROA: register of actions
	# get case number
	roa = soup.find(class_="ssCaseDetailCaseNbr")
	d[roa.contents[0].strip().encode('utf-8')] = roa.contents[1].get_text().encode('utf-8')

	# get all other data from top right table
	# type of case
	for i in range(0,5):
		d[h[i].get_text().encode('utf-8').strip(":")] = h[i].next_sibling.get_text().encode('utf-8') 

	# find all headings of interest:
	h = soup.find_all("th","ssEventsAndOrdersSubTitle")

	if len(soup.find_all(text="DISPOSITIONS")) > 0:

		# cases before 2009 have a nicely formatted <pre> block
		if len(soup.findAll("pre")) > 0:
			d["data"] = True
			res = soup.findAll("pre")
			# get date
			res1 = res[0].contents[0].split("\n")
			d["EntryDate"] = res1[0].split(":")[1].split("@")[0].encode('utf-8').strip()

			# get all the other data
			for e in res1[1:]:
				if len(e) > 0:
					s = e.split(":")
					d[s[0]] = s[1]

		else:
			# have to tease it out
			d["data"] = True
			disp = soup.find("td",headers="CDisp RDISPDATE1")
			# go on:
			d["Disposition"]= disp.contents[0].get_text().encode('utf-8')
			d["Judge"] = disp.contents[1].encode('utf-8').strip(" or ( or )")
			rows = disp.contents[3].find_all("tr")
			for r in rows:
				data = map(parse_string, r.findAll("td"))[0]
				# print(data)
				if len(data) > 0:
					if data.count(":") == 1:
						s = data.split(":")
						d[s[0]] = s[1:]
					elif data.count(":") == 2 and "," in data:
						s = data.split(",")
						s1 = s[0].split(":")
						d[s1[0]] = s1[1]
						s1 = s[1].split(":")
						d[s1[0]] = s1[1]
					else:
						d["data"] = False
						# print "in case number %s" % d["Case No."]
						# print "no data in CDisp RDISPDATE1 collected"
	else:
		d["data"] = False
		# print "in case number %s" % d["Case No."]
		# print "not collecting any data"
	# print "got data: %s" % repr(d["data"])
	driver.back()
	return d


def writeUnicode(s,file):
	""" write unicode string s to file as utf-8 encoded
	string"""
	with codecs.open(file,"w",encoding="utf-8") as f:
		f.write(s)



# run the scraper:

banks =["WELLS FARGO BANK","US BANK"]
# banks =["WELLS FARGO BANK","US BANK","CITIBANK","DEUTSCHE BANK NA TRUS","BAC HOME LOAN SERVICI","JP MORTGAGE CHASE BANK","CHASE HOME FINANCE","HSBC ","BANK OF AMERICA","GMAC ","PNC NATIONAL BANK","BANK OF NEW YORK MELL","NATIONAL CITY BANK","AURORA LOAN SERVICES","LASALLE BANK NA","PROVIDIAN NATIONAL BANK","NEVADA STATE BANK","WASHINGTON MUTUAL","CAPITAL ONE","ONE NEVADA CREDIT UNION","AMERICA FIRST CREDIT UNION","CLARK COUNTY CREDIT UNION","WEST STAR CREDIT UNION","PLUS CREDIT UNION","STAGE EMPLOYEES FEDERAL CREDIT UNION"]
dates = [("01/01/2000","01/01/2008"),("01/01/2008","01/01/2015")]





# write to file
# with open('output.txt', 'w') as f:
#     for tr in soup.find_all('tr')[2:]:
#         tds = tr.find_all('td')
#         f.write("Nome: %s, Cognome: %s, Email: %s\n" % \
#               (tds[0].text, tds[1].text, tds[2].text))


def parse_string(el):
   text = ''.join(el.findAll(text=True))
   return text.strip()

# iterate over tables
# for idx, elts in enumerate(soup.find_all("table")):
# 	print "idx = %d" % idx
# 	if idx == 5:
# 		print(type(elts))
# 		print(dir(elts))
# 		print(elts.children)
# 		trs = elts.findAll("tr")
# 		for tds in trs.findAll("td"):
# 			print "case id %s" % tds[0].text


if __name__ == "__main__":
    launchScraper()

