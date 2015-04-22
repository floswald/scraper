from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, ElementNotVisibleException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from codecs import open
import os
from json import load, dump


# http://stackoverflow.com/questions/989872/how-do-i-draw-out-specific-data-from-an-opened-url-in-python-using-urllib2/989920#989920





class Driver:
    def __init__(self, url):
        self.baseurl = url
        self.driver = webdriver.Firefox()
        self.driver.get(url)

    def goSearch(self):
        if self.getURL() is not self.baseurl:
            self.goHome()
        self.driver.find_element_by_link_text("District Civil/Criminal Records").click()

    def getSource(self):
        self.driver.page_source

    def getURL(self):
        self.driver.current_url

    def goHome(self):
        self.driver.get(self.baseurl)


class Bank:
    def __init__(self, bname, Driver):
        self.bankname = bname
        self.browser = Driver
        self.dates = ('no from', 'no to')
        self.currentCase = 'none'
        self.cases = {}
        self.casesToGo = {}
        self.done = False
        self.searchURL = 'none'
        self.fname = 'none'
        self.data = {'bank': bname, 'caseCount': 0, 'done': False, 'dates_from': "0", "dates_to": "0",
                     'currentCase': 'none'}

    def submitSearch(self, dates):
        """ submits a search query for bank
		at dates. browser will display search results"""

        assert len(dates) == 2
        self.dates = dates
        self.data["date_from"] = self.dates[0]
        self.data["date_to"] = self.dates[1]

        # move browser to district court search
        # if self.browser.driver.current_url is self.browser.baseurl:
        self.browser.goSearch()

        try:
            downelt = WebDriverWait(self.browser.driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//select[@id='SearchBy']")))
            ddown = Select(downelt)
        except ElementNotVisibleException:
            print "waited for 30 seconds to load search page. quitting driver."
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
            downelt = WebDriverWait(self.browser.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//select[@id='SearchBy']")))
            ddown = Select(downelt)
        except ElementNotVisibleException:
            print "waited for 15 seconds to load search page. quitting driver."
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


    def setCases(self, cases):
        self.cases = cases
        self.casesToGo = cases
        self.currentCase = cases.keys()[0]

    def caseDone(self):
        self.casesToGo.pop(self.currentCase)  # get rid of current case
        if len(self.casesToGo) == 0:
            self.done = True
        else:
            self.currentCase = self.casesToGo.keys()[0]  # replace current case

    def parseCaseList(self, term):
        """ get the HTML source of the current page_source
		and save the dict of relevant cases """

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
        print "    searching for %s turns up %d cases" % (term, len(rows[3:]))
        self.setCases(BoCcases)


    def parseSingleCase(self):
        """parse the current case"""

        soup = BeautifulSoup(self.browser.driver.page_source)

        # dict
        d = {}

        # get URL of this case. useless as far as I can see.
        d["URL"] = self.browser.driver.current_url.encode('utf-8')

        print "parsing URL %s" % d["URL"]

        # get all table headers	of that class:
        h = soup.find_all(class_="ssTableHeaderLabel")

        # ROA: register of actions
        # get case number
        roa = soup.find(class_="ssCaseDetailCaseNbr")
        d[roa.contents[0].strip().encode('utf-8')] = roa.contents[1].get_text().encode('utf-8')

        # get all other data from top right table
        # type of case
        for i in range(0, 5):
            d[h[i].get_text().encode('utf-8').strip(":")] = h[i].next_sibling.get_text().encode('utf-8')

        # find all headings of interest:
        h = soup.find_all("th", "ssEventsAndOrdersSubTitle")

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
                        d[s[0]] = s[1]

            else:
                # have to tease it out
                disp = soup.find("td", headers="CDisp RDISPDATE1")
                # go on:
                d["Disposition"] = disp.contents[0].get_text().encode('utf-8')
                d["Judge"] = disp.contents[1].encode('utf-8').strip(" or ( or )")
                rows = disp.contents[3].find_all("tr")
                for r in rows:
                    data = map(parse_string, r.findAll("td"))[0]
                    # print(data)
                    if len(data) > 0:
                        if data.count(":") == 1:
                            s = data.split(":")
                            d[s[0]] = s[1:]
                            d["hasData"] = True
                        elif data.count(":") == 2 and "," in data:
                            s = data.split(",")
                            s1 = s[0].split(":")
                            d[s1[0]] = s1[1]
                            s1 = s[1].split(":")
                            d[s1[0]] = s1[1]
                            d["hasData"] = True
                        else:
                            d["hasData"] = False
                        # print "in case number %s" % d["Case No."]
                        # print "no data in CDisp RDISPDATE1 collected"
        else:
            d["hasData"] = False
        # print "in case number %s" % d["Case No."]

        # save data into self.data
        self.data[self.currentCase] = d


    def startBankSearch(self, dates):
        self.submitSearch(dates)
        self.caseCount = 0
        try:
            WebDriverWait(self.browser.driver, 15).until(EC.presence_of_element_located(
                (By.XPATH, "/html/body/table[4]/tbody/tr[1]/th[1][@class='ssSearchResultHeader']/b")))
            self.parseCaseList("Breach of Contract")
        except NoSuchElementException:
            print "could not get results table"
            self.browser.driver.quit()

        # set up filename
        path = os.path.join('.', self.bankname)
        if not os.path.isdir(path):
            os.makedirs(path)
        self.fname = os.path.join(path, ''.join([dates[0].strip("/"), ".json"]))
        print "saving to filename %s" % self.fname
        # run the search
        self.continueBankSearch()


    def continueBankSearch(self):

        while self.done is not True:

            # check if browser is on search results page
            # if self.checkSearch():
            #     self.reSubmitSearch()

            case = self.currentCase
            self.caseCount = self.caseCount + 1
            print "trying case %s" % case
            try:
                self.browser.driver.find_element_by_link_text(case).click()  #click on the required link to access a single case
                self.parseSingleCase()  # get individual case data
                self.browser.driver.back()  #  bring browser back on page
                self.browser.driver.implicitly_wait(1)  # and wait 1 second
            except NoSuchElementException:
                print "could not open link for case %s" % case
                print "trying to reset the browser"
                self.browser.driver.goHome()
                self.browser.driver.goSearch()
                self.reSubmitSearch()
                self.browser.driver.implicitly_wait(1)  # and wait 1 second
                pass
            except AttributeError:
                print "could not parse case %s" % case
                pass

            self.data['caseCount'] = self.caseCount
            self.data['currentCase'] = case

            if self.caseCount % 10 is 0:
                self.updateData()

            # tick off this case as done
            self.caseDone()

    def updateData(self):
        f = open(self.fname, 'rw')
        d = json.load(f)
        d.update(self.data)
        json.dump(d, f)
        f.close()


# run the scraper:

banks = ["WELLS FARGO BANK", "US BANK"]
# banks =["WELLS FARGO BANK","US BANK","CITIBANK","DEUTSCHE BANK NA TRUS","BAC HOME LOAN SERVICI","JP MORTGAGE CHASE BANK","CHASE HOME FINANCE","HSBC ","BANK OF AMERICA","GMAC ","PNC NATIONAL BANK","BANK OF NEW YORK MELL","NATIONAL CITY BANK","AURORA LOAN SERVICES","LASALLE BANK NA","PROVIDIAN NATIONAL BANK","NEVADA STATE BANK","WASHINGTON MUTUAL","CAPITAL ONE","ONE NEVADA CREDIT UNION","AMERICA FIRST CREDIT UNION","CLARK COUNTY CREDIT UNION","WEST STAR CREDIT UNION","PLUS CREDIT UNION","STAGE EMPLOYEES FEDERAL CREDIT UNION"]
dates = [("01/01/2000", "01/01/2008"), ("01/01/2008", "01/01/2015")]

if __name__ == "__main__":
    d = Driver("https://www.clarkcountycourts.us/Anonymous/default.aspx")
    for b in banks:
        bb = Bank(b, d)
        bb.startBankSearch(dates[0])

