#Stuff we need to work with the file system, create filenames, etc.
#Aha -- a change!
import os
from cmd2 import Cmd
import time
import sys
import re
import io
import time
import uuid
import json

#Stuff we'll need for data analysis (later on in development)
import pandas as pd

#Stuff we'll need for interacting with the DC Courts system, via Chrome
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait as wait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

#Stuff we'll need for OCRing PDFs the program encounters
from wand.image import Image
from PIL import Image as PI
from tesserocr import PyTessBaseAPI, RIL

#Import all the subroutines that sit behind the shell
from subroutines import *

#Define the shell script and all of its commands
class DcCourtCollector(Cmd):
    intro =  """
        DC Court Collector
        Tool for iterating through DC Court's eAccess System
        and Collecting Public Records for analysis

        Type help or ? to list commands.
        """
    prompt = '[DC Court Data]: '

    def __init__(self):
        Cmd.__init__(self)

    def do_cleanupData(self,arg):
        """The collection tool sometimes runs into issues when browsing the DC eAccess
        site that cause it to fail. When this happens, the temporary JSON files it creates
        to store collected cases are left behind, and some downloaded documents are not OCR'ed.
        Run cleanupData to consolidate these temporary JSON files.
        If you want to quickly view the JSON contents for a particular case, add the case reference
        as an argument.
        Ex: cleanupData
        Ex: cleanupData 18LTB132
        """
        cleanup_data()

        #Open the final.json again, this time to read it and print a sorted list of its
        #keys for the shell user
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'final.json')) as file:
            data = file.read()
            data = json.loads(data)

        #If the user didn't ask to see a particular case, produce a quick list of all cases
        #now contained in final.json
        if arg == "":
            keys = data.keys()
            for id in sorted(keys):
                print(id)
        #If the user did ask to see a particular case, print the json for that case on the screen
        else:
            case = parse_caseref(arg)
            print(data[case['string']])

    def do_cleanupDocs(self,arg):
        """The collection tool sometimes runs into issues when browsing the DC eAccess
        site that cause it to fail. When this happens, the temporary JSON files it creates
        to store collected cases are left behind, and some downloaded documents are not OCR'ed.
        Run cleanupData to OCR any outstanding documents. The program also deletes any
        downloaded PDFs that were not properly associated with a case due to an error.
        Ex: cleanupDocs
        """
        cleanup_docs()

    def do_collectCases(self,arg):
        """Open a Selenium window into the \n DC Court's eAccess page, then provide
        an abbreviated case reference (e.g., 18LTB12) as a starting point, then the
        number of cases you want to collect, or another case reference, as an end
        point. The tool will attempt to collect all of the cases, including any attached
        documents. When it completes its collection run, it will attempt to OCR any
        attached documents it found
        Ex: collectCases
        """

        #initialize the web browser
        #(the in-browser PDF viewer needs to be disabled
        # to force the PDFs the program opens to download)
        download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'case_data' , 'case_documents')
        chrome_options = Options()
        chrome_options.add_experimental_option('prefs',{
            "plugins.plugins_list" : [{"enabled": False, "name": "Chrome PDF Viewer"}],
            "download": {
                "prompt_for_download": False,
                "default_directory": download_dir,
                "directory_upgrade": True,
            }
        })

        #Requires the most recent driver for Chrome (to match the
        #Chrome installation on the machine)
        #https://sites.google.com/a/chromium.org/chromedriver/downloads
        #(You may need to include the path to the driver as your first
        #variable in webdriver.Chrome, if the webdriver is not in your PATH)
        browser = webdriver.Chrome(chrome_options = chrome_options)

        #Identify the court access portal
        url = 'https://eaccess.dccourts.gov/eaccess/'

        #Fetch the court access portal homepage
        browser.get(url)

        #Prompt the user to answer the captcha
        captcha = input("When the page has /completely/ finished loading,\nenter the captcha text here.\n(The loading wheel may spin for quite awhile...)\n[Captcha]: ")

        #Clear the captcha form, then enter the captcha & submit
        browser.find_element_by_id('id3').clear()
        browser.find_element_by_id('id3').send_keys(captcha)
        browser.find_element_by_css_selector('a.anchorButton').click()


        #Wait for the captcha to be accepted and for the page to move to the search page...
        #(By checking for the presence of an element found only on the search page)
        wait(browser,15).until(EC.presence_of_element_located((By.ID,"caseDscr")))

        search_page = browser.current_url

        start = input("Enter the abbreviated case number for the first case you'd like to collect (e.g., 16LTB5701).\n[Case Ref]: ")

        end = input("Enter the abbreviated case number for the last case you'd like to collect (e.g., 16LTB8301)\n   --OR--  \nenter the number of cases you'd like to collect.\n[Number or Case Ref]: ")

        #Parse the abbreviated case references into their constituent parts
        case = parse_caseref(start)

        #If the user entered an end number, the program will iterate through that many cases
        #If the user entered an end case, the program will calculate the number of cases
        #to scrape by subtracting the end case number from the beginning one
        collection_count = 0

        if type(end) is int:
            collection_limit = end
        #Otherwise, parse the end case reference and deduce the number of cases by subtracting
        #it's case number from the starting case's number
        else:
            end_case = parse_caseref(end)
            collection_limit = int(end_case['caseno'] ) - int(case['caseno'])

        #Generate a stamp for the temporary JSON file that will store the data by using the current time
        datastamp = str(time.time())[:-3]

        #Create an empty opject for the cases we collect
        cases = []

        #Name a storage file (where we're keeping the data as json for now, until I have time to set up a
        #database for it)
        case_storage = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'case_data' , str(uuid.uuid4()) + '.json')

        #While the program is within the range of cases the user requested...
        while (collection_count <= collection_limit):
            print("Collecting case " + case['string'] + "...")

            collect_case(search_page,browser,case['string'],cases)

            #Iterate to the next case
            case['caseno'] = int(case['caseno']) + 1
            case = parse_caseref(case)
            collection_count = collection_count + 1

            #Drop the new version of the cases list (with the just-collected case) into a JSON string
            output = json.dumps(cases)
            #Overwrite the file where the cases are stored with the new case list
            #(This isn't super efficient, but it'll do until the program has a database,
            #and it prevents data from being lost if the connection to the Court website
            # fails for some reason)
            with open(case_storage,"w") as storage:
                storage.write(output)
            #Pause for 4 seconds (DC Bar requested this setting, to be respectful of DC Courts)
            time.sleep(4)

        #Consolidate temporary JSON files into a single "final.json" file
        cleanup_data()

        #AFTER completely collecting all cases, the program attempts to OCR them
        #(otherwise, the OCR process can take so long that the connection to the
        #court system times out)
        cleanup_docs()

#Instantiate the shell script
if __name__ == '__main__':
    app = DcCourtCollector()
    app.cmdloop()
