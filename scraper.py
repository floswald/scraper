from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, ElementNotVisibleException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from codecs import open
import os
import json
import copy
from datetime import datetime, timedelta
import re


# 
    



class NoCasesException(Exception):
	pass

class BrowserErrorException(Exception):
    pass


class Driver:
    def __init__(self, url, wait=30):
        self.baseurl = url
        self.driver = webdriver.Firefox()
        self.driver.get(url)
        self.wait = wait

    def goSearch(self):
        if self.getURL() is not self.baseurl:
            self.goHome()
            try: 
                WebDriverWait(self.driver, self.wait).until(EC.presence_of_element_located((By.LINK_TEXT, "District Civil/Criminal Records")))
                self.driver.find_element_by_link_text("District Civil/Criminal Records").click()
            except NoSuchElementException:
                print "server is hung after %d secs. restart. please wait." % self.wait
                self.driver.implicitly_wait(self.wait)
                self.goHome()
                self.driver.refresh()
                self.goSearch()

    def getSource(self):
        self.driver.page_source

    def getURL(self):
        self.driver.current_url

    def goHome(self):
        self.driver.get(self.baseurl)


class Bank:
    def __init__(self, bname, Driver, init_dates):
        self.bankname = bname
        self.browser = Driver
        self.currentCase = 'none'
        self.cases = {}
        self.casesToGo = {}
        self.done = False 	# current search over subset of date range done
        self.doneRange = False	# search over entire date range done: get new date range, or exit
        self.searchURL = 'none'
        self.fname = 'none'
        self.changeDates = True
        assert len(init_dates) == 2
        self.dates = copy.deepcopy(init_dates)
        self.submittedDates = copy.deepcopy(init_dates)
        self.data = {'bank': bname, 'caseCount': 0, 'done': False, 'dates_from': "0", "dates_to": "0",
                     'currentCase': 'none', 'cases' : {}, 'not_parsed' : []}
        print "set up Bank %s from %s to %s" % (self.bankname, self.dates[0],self.dates[1])


    def checkCaseList(self):
        """see if the result table has a red 
        heading with TOO MANY CASES, and restrict the 
        time frame if it is the case"""
        soup = BeautifulSoup(self.browser.driver.page_source)
        tag = soup.findAll("td",align="center",style="color:#FF4040")
        if len(tag) > 0 and "too many matches" in tag[0].contents[0].get_text():
            self.changeDates = True
            df               = "%m/%d/%Y"
            todate           = datetime.strptime(self.dates[1], df)
            fromdate         = datetime.strptime(self.dates[0], df)
            delta            = (todate - fromdate) / 2
            newto            = (fromdate + delta).strftime(df)
            print "too many results for %s - %s" % (self.dates[0],self.dates[1])
            print "changed search to end on %s" % newto
            self.dates[1] = newto
            print "resubmitting search now"
            self.reSubmitSearch()
        else:
            self.changeDates = False


    def setCases(self, cases):
        self.cases = cases
        self.casesToGo = cases
        self.currentCase = cases.keys()[0]

    def caseDone(self,currentCase):
        self.casesToGo.pop(currentCase)  # get rid of current case
        # print "number cases to go %d:" % len(self.casesToGo.keys())
        if len(self.casesToGo) == 0 and self.dates[1] == self.submittedDates[1] :
            self.done = True
            self.doneRange = True
        elif len(self.casesToGo) == 0 and self.dates[1] != self.submittedDates[1]:
            self.done = True
            self.doneRange = False
        else:
            self.currentCase = self.casesToGo.keys()[0]  # replace current case and go on

	def cleanDates(self):
		self.dates = ['0','0']
		self.submittedDates = ['0','0']

    # parsing functions
    # =================

    def parseCaseList(self, term):
        """ get the HTML source of the current page_source
		and save the dict of relevant cases. Also raise
		and exception if no cases are found at all."""

        soup = BeautifulSoup(self.browser.driver.page_source)

        # Breach of Contract cases
        BoCcases = {}
        # get the results table
        tab = soup.find_all("table")[5:]  # look in index 5 onwards
        rows = tab[0].findAll('tr')
        for rowv in rows[3:]:
            cols = rowv.findAll('td')
            if term in cols[4].text:
                BoCcases[cols[0].text] = rowv

        self.numcases = len(BoCcases)
        print "searching for %s turns up %d cases" % (term, self.numcases)
        print ""
        if self.numcases == 0:
        	raise NoCasesException("No Cases found in %s for %s - %s" % (self.bankname, self.dates[0], self.dates[1]))
        else:
	        self.setCases(BoCcases)





    def parseSingleCase(self):
        """parse the current case"""

        soup = BeautifulSoup(self.browser.driver.page_source)

        # TODO check if this an error page:
        errors = soup.find_all(class_="ssHeaderTitleBanner")        
        if len(errors) > 0 and "Public Access Error" in errors[0].get_text():
            raise BrowserErrorException

        # dict
        d = {}

        # get URL of this case. useless as far as I can see.
        d["URL"] = self.browser.driver.current_url.encode('utf-8')

        # print "parsing URL %s" % d["URL"]

        # get all table headers	of that class:
        h = soup.find_all(class_="ssTableHeaderLabel")

        # ROA: register of actions
        # get case number
        roa = soup.find(class_="ssCaseDetailCaseNbr")
        caseid = roa.contents[1].get_text().encode('utf-8')
        #add ID prefix to case id?
        #d[roa.contents[0].strip().encode('utf-8')] = ''.join(['ID_',caseid])
        d[roa.contents[0].strip().encode('utf-8')] = caseid

        # get all other data from top right table
        # type of case
        for i in range(0, 5):
            d[h[i].get_text().encode('utf-8').strip(":")] = h[i].next_sibling.get_text().encode('utf-8')

        # get Party Information table
        parties = soup.find_all("caption",text="Party Information")[0].parent
        defendants = parties.findAll("th",text="Defendant")
        idcount = 0
        for defe in defendants:
            idcount += 1
            d[''.join([defe.get_text().encode('utf-8').strip(),"_",str(idcount)])] = defe.next_sibling.get_text().encode('utf-8').strip()

        plaintiffs = parties.findAll("th",text="Plaintiff")
        idcount = 0
        for defe in plaintiffs:
            idcount += 1
            d[''.join([defe.get_text().encode('utf-8').strip(),"_",str(idcount)])] = defe.next_sibling.get_text().encode('utf-8').strip()

        if len(soup.find_all(text="DISPOSITIONS")) > 0:

            # cases before 2009 have a nicely formatted <pre> block
            if len(soup.findAll("pre")) > 0:
                d["hasData"] = True
                res = soup.findAll("pre")
                # get date
                res1 = res[0].contents[0].split("\n")
                d["EntryDate"] = res1[0].split(":")[1].split("@")[0].encode('utf-8').strip()

                # get all the other data
                for e in res1[1:]:
                    if len(e) > 0:
                        s = e.split(":")
                        d[s[0]] = s[1].encode('utf-8').strip()

            else:
                # have to tease it out
                disp = soup.find("td", headers="CDisp RDISPDATE1")
                # go on:
                
                # sometimes the main disposition is indented (multiple dispositions), and then the first element is a date
                match = re.search(r'(\d+/\d+/\d+)',disp.contents[0].get_text())
                if match is None:
                    addidx = 0
                else:
                    addidx = 1

                d["Disposition"] = disp.contents[0+addidx].get_text().encode('utf-8').strip()
                d["Judge"] = disp.contents[1+addidx].encode('utf-8').strip(" or ( or )").strip()
                rows = disp.contents[3+addidx].find_all("tr")
                if len(rows) > 0:
                    d["hasData"] = True
                    for r in rows:
                        data = map(parse_string, r.findAll("td"))[0]
                        # print(data)
                        if len(data) > 0:
                            if data.count(":") == 1:
                                s = data.split(":")
                                d[s[0]] = s[1].encode('utf-8').strip()
                            elif data.count(":") == 2 and "," in data:
                                s = data.split(",")
                                s1 = s[0].split(":")
                                d[s1[0]] = s1[1].strip()
                                s1 = s[1].split(":")
                                d[s1[0]] = s1[1].strip()
                                                                       
                                                                           
        else:
            d["hasData"] = False
        # print "in case number %s" % d["Case No."]

        # save data into self.data
        self.data['cases'][self.currentCase] = d



    # Submit Search functions
    # =======================

    def startBankSearch(self):
        self.submitSearch()
        self.caseCount = 0
        print "started search from %s to %s" % (self.dates[0],self.dates[1])
        try:
            WebDriverWait(self.browser.driver, 15).until(EC.presence_of_element_located(
                (By.XPATH, "/html/body/table[4]/tbody/tr[1]/th[1][@class='ssSearchResultHeader']/b")))

            while self.changeDates:
            	self.checkCaseList()

            self.parseCaseList("Breach of Contract")
        except NoCasesException:
            return 0
        except NoSuchElementException:
            print "could not get results table"
            self.browser.driver.quit()

        # set up filename
        path = os.path.join(os.getcwd(), 'output', self.bankname.replace(" ","_"))
        if not os.path.isdir(path):
            os.makedirs(path)
        self.fname = os.path.join(path, ''.join([self.dates[0].replace("/",""),"-",self.dates[1].replace("/",""), ".json"]))
        if os.path.isfile(self.fname):
        	os.remove(self.fname)
        print "saving to filename %s" % self.fname

        # check it 
        # run the search
        self.data["dates_from"] = self.dates[0]
        self.data["dates_to"] = self.dates[1]
        retval = self.continueBankSearch()
        return retval


    # def warmStart(file):
    	# load file
    	# start browser
    	# start bank
    	# fill in dates
    	# set self.currentCase = data["currentCase"]
    	# call 

    def submitSearch(self):
        """ submits a search query for bank
		at dates. browser will display search results"""

        # assert len(dates) == 2
        # self.dates[0] = dates[0]
        # self.dates[1] = dates[1]

        # store submitted dates so I know if have to continue or if this is last batch
        # self.submittedDates = dates

        # move browser to district court search
        # if self.browser.driver.current_url is self.browser.baseurl:
        self.browser.goSearch()

        try:
            downelt = WebDriverWait(self.browser.driver, self.browser.wait).until(
                EC.presence_of_element_located((By.XPATH, "//select[@id='SearchBy']")))
            ddown = Select(downelt)
        except ElementNotVisibleException:
            print "waited for %d seconds to load search page. quitting driver." % self.browser.wait
            self.browser.driver.quit()

        ddown.select_by_visible_text("Party")
        # click on radio button "Business"
        self.browser.driver.find_element_by_xpath("//input[@id='PartyBusinessOption']").click()
        # fill in name of bank we are looking for
        self.browser.driver.find_element_by_xpath("//input[@id='LastName']").send_keys(self.bankname)
        # could specify dates here:
        self.browser.driver.find_element_by_xpath("//input[@id='DateFiledOnAfter']").send_keys(self.dates[0])
        self.browser.driver.find_element_by_xpath("//input[@id='DateFiledOnBefore']").send_keys(self.dates[1])
        # submit the search

        self.browser.driver.find_element_by_xpath("//input[@id='SearchSubmit']").click()
        self.browser.driver.implicitly_wait(2)

        # store the URL of search results: list of cases
        self.searchURL = self.browser.driver.current_url

    def checkSearch(self):
        if self.browser.driver.current_url is not self.searchURL:
            self.browser.goSearch()
            print "checkSearch has reset the browser to search district courts"
            return True
        else:
            return False

    def reSubmitSearch(self):
        # move browser to district court search
        self.browser.goSearch()

        try:
            downelt = WebDriverWait(self.browser.driver, self.browser.wait).until(
                EC.presence_of_element_located((By.XPATH, "//select[@id='SearchBy']")))
            ddown = Select(downelt)
        except ElementNotVisibleException:
            print "waited for %d seconds to load search page. quitting driver." % self.browser.wait
            self.browser.driver.quit()
        ddown.select_by_visible_text("Party")
        # click on radio button "Business"
        self.browser.driver.find_element_by_xpath("//input[@id='PartyBusinessOption']").click()
        # fill in name of bank we are looking for
        self.browser.driver.find_element_by_xpath("//input[@id='LastName']").send_keys(self.bankname)
        # could specify dates here:
        self.browser.driver.find_element_by_xpath("//input[@id='DateFiledOnAfter']").send_keys(self.dates[0])
        self.browser.driver.find_element_by_xpath("//input[@id='DateFiledOnBefore']").send_keys(self.dates[1])
        # submit the search
        self.browser.driver.find_element_by_xpath("//input[@id='SearchSubmit']").click()
        # store the URL of search results: list of cases
        self.searchURL = self.browser.driver.current_url

    def continueBankSearch(self):

        while self.doneRange is False:

            while self.done is False:

                case = self.currentCase
                # print "this is case [%d/%d]" % (self.caseCount, self.numcases)
                # print "trying case %s" % case
                try:
                    link = WebDriverWait(self.browser.driver,self.browser.wait).until(EC.element_to_be_clickable((By.LINK_TEXT,case)))
                    link.click()  #click on the required link to access a single case
                    self.parseSingleCase()  # get individual case data
                    self.caseDone(case)
                    self.caseCount = self.caseCount + 1
                    self.browser.driver.implicitly_wait(1)  # give browser a break
                    self.browser.driver.back()  #  bring browser back on page
                except TimeoutException:
                    # print "could not open link for case %s" % case
                    # print "trying to reset the browser"
                    self.data['cases'][self.currentCase] = { "hasData" : False }
                    self.caseDone(case)
                    self.caseCount = self.caseCount + 1
                    self.browser.goHome()
                    self.browser.goSearch()
                    self.reSubmitSearch()
                    pass
                except AttributeError:
                    self.browser.driver.back()  #  bring browser back on page
                    self.caseDone(case)
                    self.caseCount = self.caseCount + 1
                    self.data['not_parsed'].append(case)
                    print "could not parse case %s because of AttributeError" % case
                    print ""
                    pass
                except BrowserErrorException:
                    print "browser responds with error. reset."
                    self.browser.goHome()
                    self.browser.goSearch()
                    self.reSubmitSearch()
                    pass

                self.data['caseCount'] = self.caseCount
                self.data['currentCase'] = case

                if self.caseCount % 20 is 0:
                    self.updateData()

            if self.doneRange is False:
                # get new date range
                # get final date of last search:
                self.updateData()
                todate = datetime.strptime(self.dates[1],"%m/%d/%Y")
                newfromdate = todate + timedelta(days = 1)
                self.dates[0] = newfromdate.strftime("%m/%d/%Y")
                self.dates[1] = self.submittedDates[1]
                self.done = False
                print "submitting search for %s - %s" % (self.dates[0],self.submittedDates[1])
                self.startBankSearch()
            else:
                self.updateData()
                print ""
                print "finished search in %s" % self.bankname
                print ""

        # return control to upper loop
        return 0


    def updateData(self):
        f = open(self.fname, 'w')
        json.dump(self.data, f)
        f.close()
        print "saved data at case [%d/%d]" % (self.caseCount,self.numcases)
        print "to file %s" % self.fname

        #     print "created %s" % self.fname
        # else:
        #     print "trying to update %s" % self.as
        #     f = open(self.fname, 'w')
        #     d = json.load(f)
        #     d.update(self.data)
        #     json.dump(d,f)
        #     f.close()


# global functions

def parse_string(el):
   text = ''.join(el.findAll(text=True))
   return text.strip()

# run the scraper:
# banks = ["NATIONAL CITY BANK","AURORA LOAN SERVICES","LASALLE BANK NA","PROVIDIAN NATIONAL BANK","NEVADA STATE BANK","WASHINGTON MUTUAL","CAPITAL ONE","ONE NEVADA CREDIT UNION","AMERICA FIRST CREDIT UNION","CLARK COUNTY CREDIT UNION","WEST STAR CREDIT UNION","PLUS CREDIT UNION","STAGE EMPLOYEES FEDERAL CREDIT UNION"]
    # banks = ["US BANK"]
    #banks =["WELLS FARGO BANK","US BANK","CITIBANK","DEUTSCHE BANK NA TRUS","BAC HOME LOAN SERVICI","JP MORTGAGE CHASE BANK","CHASE HOME FINANCE","HSBC ","BANK OF AMERICA","GMAC ","PNC NATIONAL BANK","BANK OF NEW YORK MELL","NATIONAL CITY BANK","AURORA LOAN SERVICES","LASALLE BANK NA","PROVIDIAN NATIONAL BANK","NEVADA STATE BANK","WASHINGTON MUTUAL","CAPITAL ONE","ONE NEVADA CREDIT UNION","AMERICA FIRST CREDIT UNION","CLARK COUNTY CREDIT UNION","WEST STAR CREDIT UNION","PLUS CREDIT UNION","STAGE EMPLOYEES FEDERAL CREDIT UNION"]
    # banks =["US BANK","NEVADA STATE BANK","ONE NEVADA CREDIT UNION","AURORA LOAN SERVICES","LASALLE BANK NA","CLARK COUNTY CREDIT UNION","STAGE EMPLOYEES FEDERAL CREDIT UNION"]

def run():
	
    banks = ["GMAC","PROVIDIAN NATIONAL BANK"]
    # provide 2 time spans by default
    dateSpan = ["01/01/2000", "01/01/2015"]
    dr = Driver("https://www.clarkcountycourts.us/Anonymous/default.aspx",30)
    for b in banks:
    	print ""
    	print "starting to search: %s" % b
    	print "==========================="
    	print ""
    	bb = Bank(b, dr, dateSpan)
    	retval = bb.startBankSearch()
        bb.cleanDates()
    
    print "scraper finished with:"
    print banks
    print "exiting."
    dr.driver.quit()
    return 0

if __name__ == "__main__":
	run()

