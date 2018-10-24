import sys
import re
import os
import io
import time
import uuid
import json

#Stuff we'll need for data analysis
import pandas

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

#
def cleanup_docs():
    #Document data should be stored within the "case_data" folder, in a subfolder called "case_documents"
    doc_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'case_data' , 'case_documents')

    #Iterate through all the files in case_documents
    for file in os.listdir(doc_dir):
        #If the file is a PDF...
        if file.endswith(".pdf"):
            #If it is a search.page.pdf (auto-downloaded file that wasn't propertly renamed,
            # delete it)
            if file.startswith('search') or os.path.getsize(os.path.join(doc_dir,file)) == 0:
                os.unlink(os.path.join(doc_dir,file))
                #Otherwise, check to see if the file was already OCRed (if it was, an HOCR file with
                #the same name should exist)
            else:
                name = file.replace('.pdf','.hocr')
                #If there is no HOCR file that corresponds to this PDF
                if not os.path.isfile(os.path.join(doc_dir,name)):
                    #Report on progress...
                    print('OCRing ' + name + '...')
                    #And OCR the file
                    ocr_pdf(os.path.join(doc_dir,file))

#Cleanup tempoary JSON files, consolidating them into a single "final.json" file
def cleanup_data():
    #Case data should be stored in the same folder as the script files, in a subfolder called "case_data"
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'case_data')

    #Open the current version of "final.json" (the json file in the root folder that is currently
    #where all collected cases are stored) and read it into a variable
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'final.json'),'r') as final_file:
        data = final_file.read()
        final = json.loads(data)

    #Assume no updates are necessary
    update = False

    #Iterate through the files in the case_data folder
    for file in os.listdir(data_dir):
        #Whenever you find a json file
        if file.endswith(".json"):
            #Note that the program had updates to make to the final.json file
            update = True
            #Open the json file found in case_data
            with open(os.path.join(data_dir,file),'r') as data_file:
                #Read its information into a variable
                data = data_file.read()
                data = json.loads(data)
                #Iterate through all cases in the temporary data file, adding them
                #to the final data variable
                for case in data:
                    case_id = case['case_id']
                    if len(case['Plaintiff']) > 0:
                        final[case_id] = case
            #Delete the temporary json file
            os.unlink(os.path.join(data_dir,file))

        #If the program has updates to make, write the new version of the final
        #case data dictionary to final.json
        if update:
            with open('final.json', 'w') as file_out:
                json.dump(final, file_out)

#Parse an abbreviated case reference into an object containing the caseref's
#constitutent parts and also a string with the extended version of the caseref
#--OR---
#Update the full string reference contained within a caseref object whose parts have
#been modified elsewhere
def parse_caseref(caseref):
    #If the input is a string, we're building the case object from scratch
    if type(caseref) == str:
        case = {
            'year': caseref[:2],
            'docket': re.search('[a-z]+',caseref,re.IGNORECASE).group(0),
            'caseno': re.search('[0-9]+$',caseref).group(0)
            }
        case['string'] = '20' + case['year'] + ' ' + case['docket'] + ' ' + str(case['caseno']).zfill(6)
        return case
    #If the input is a case object, we're just updating its string
    if type(caseref) == dict:
        caseref['string'] = '20' + caseref['year'] + ' ' + caseref['docket'] + ' ' + str(caseref['caseno']).zfill(6)
        return caseref

def collect_header(browser,case):
    #Identify the header columns
    header_columns = browser.find_elements_by_css_selector("#caseHeader .col")

    #Iterate through the columns in the header
    for column in header_columns:
        #The columns in the header are structured as dictionary lists, so
        #grab all the terms in the column
        terms = column.find_elements_by_css_selector('dt')
        #For each term, identify the page element containing that term and
        #grab the next sibling of that element (which should contain the term's
        #definition)
        for term in terms:
            term_name = term.text
            term_value = column.find_element_by_xpath("//*[contains(text(), '" + term_name + "')]//following-sibling::*[1]").text
            case[term_name] = term_value

def collect_parties(browser,case):
    #Identify all of the elements in the party container
    parties = browser.find_elements_by_css_selector("#ptyContainer > div")

    for party in parties:
        #Party data is stored in a single string of the form [Name] - [Role]
        #So let's split it apart and store the result
        party_string = party.find_element_by_css_selector(".subSectionHeader2 h5").text
        party_name = party_string.split(" - ")[0]
        party_role = party_string.split(" - ")[1]
        #Create an object to store party information (we'll add additional definitions later)
        party_object = { 'name': party_name }
        #Add the party to the case object (as a list item, in case there are multilple parties
        #playing that role in the case)
        case[party_role].append(party_object)
        #Mark the latest addition to that party (the last item in the list)
        current_party = case[party_role][-1]

        #Find the information within the party element about the party's disposition
        #and add that information to the current party object
        party_disposition = party.find_element_by_xpath("//*[contains(text(), 'Disposition')]//following-sibling::dd[1]").text
        current_party['Disposition'] = party_disposition

        #Check to see if the party has any attorneys
        try:
            attorneys = party.find_elements_by_css_selector(".ptyAtty div")
        except:
            attorneys = False

        #If the party has attorneys, add their information to the party's
        #entry in the case object
        if attorneys:
            current_party['Attorneys'] = []
            for attorney in attorneys:
                attorney_name = attorney.find_element_by_css_selector("dd").text
                current_party['Attorneys'].append(attorney_name)

def collect_table(browser,case,type):
    #Thankfully, several areas in the case page follow a similar format
    #so it's possible to write a general purpose tool to collect their info
    table_headers = browser.find_elements_by_css_selector("#"  + type + "Info th")
    table_rows = browser.find_elements_by_css_selector("#"  + type + "Info tr:not(.headers)")


    #Create a list of all the table headers
    headers = []
    for header in table_headers:
        headers.append(header.text)

    #Iterate through the table's rows, get the text for each
    #cell and create a dictionary for the row, where the value of the cell
    #is keyed to the corresponding header
    for row in table_rows:
        position = 0;
        row_object = {}
        cells = row.find_elements_by_css_selector("td")

        for cell in cells:
            row_object[headers[position]] = cell.text
            #If the cell is a link to a PDF, collect its link in addition to its
            #text. (If it's the PDF link column but is blank, just remove the
            #entry.)
            if headers[position] == 'Image Avail.' and cell.text == 'Image':
                try:
                    cell_id = cell.find_element_by_css_selector('a').get_attribute('href')
                    row_object['pdf_link'] = cell_id
                    del row_object['Image Avail.']
                except:
                    pass
            elif headers[position] == 'Image Avail.':
                del row_object['Image Avail.']

            position = position + 1
        #Add the row object to the case object
        if type == 'docket':
            case_key = 'Docket Items'
        else:
            case_key = type + 's'
        case[case_key].append(row_object)

def collect_pdfs(browser,case):
    #Go through the case docket we've just collected, find any
    #links to PDFs, and download them while tying them back to the Case ID
    #(along with a unique id to differentiate one document from another in
    #the same case).
    for item in case['Docket Items']:
        try:
            has_pdf = item['pdf_link']
        except:
            has_pdf = False
        #If there's a PDF associated with this docket item ...
        if has_pdf:
            #open a new tab where the docket item can be downloaded
            image = browser.execute_script("window.open('" + item['pdf_link'] + "', 'new_window')")
            #Wait 3 seconds (to make sure the download has time to finish)
            time.sleep(3)

            #If the case system delivered a working link to a PDF, the download will not have
            #opened a new tab, but if the download didn't work properly it will have opened a blank
            #tab. We'll need to mark our working tab, move to the blank tab that the failed download
            #created, close that tab, and return to the working tab.
            if len(browser.window_handles) > 1:
                current_tab = browser.current_window_handle
                last_tab = browser.window_handles[len(browser.window_handles) - 1]
                browser.switch_to_window(last_tab)
                browser.close()
                browser.switch_to_window(current_tab)
            #If the download succeeded, there will be a file in the 'case_documents' folder
            #(the default download folder) with the automatically-created name 'search.page.pdf'
            #We need to find that file and rename it with a unique filename that will relate it back to this case.
            else:
                document_id = str(uuid.uuid4())
                file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'case_data','case_documents')
                final_name = os.path.join(file_path,document_id + '.pdf')
                temp_name = os.path.join(file_path,'search.page.pdf')

                #Leave a reference to the unique id we've given this particular file in its name within the case object
                #so that we know which file is which when examining the case
                item['file_id'] = document_id
                #Also leave a full reference to the file in the case object
                item['filename'] = final_name

                #Wait for the download to complete (the file to appear in the download directory, and
                #the second tab that the download needs to close)
                while not os.path.exists(temp_name)  and len(browser.window_handles) == 1:
                    time.sleep(1)

                os.rename(temp_name,final_name)

                #Remove the references to the original file links (since they'll be
                #useless after the program closes the browser).
                del item['pdf_link']


def collect_case(search_page,browser,case_ref,cases):
    #Create a dictionary with areas for storing the value
    #(or values) the program will scrape from the various areas
    #of the DC Court System's page for the case
    case_object = {
        'case_id': case_ref,
        'Plaintiff': [],
        'Defendant': [],
        'Intervenor': [],
        'events': [],
        'dispositions': [],
        'receipts': [],
        'Docket Items': [],
    }

    #Navigate to the search page to begin looking for
    #the case we'll be collecting
    browser.get(search_page)

    #Wait for the browser to move to the search page before continuing...
    #(by checking for the presence of an element found only on the search page)
    at_search = wait_for(browser,'caseDscr')

    if at_search:
        #Clear the search box, enter the case reference, and submit
        browser.find_element_by_id('caseDscr').clear()
        browser.find_element_by_id('caseDscr').send_keys(case_ref)
        browser.find_element_by_css_selector("input[name='submitLink']").click()

        #Wait for the browser to move to the search results page before continuing...
        #(by checking for the presence of an element found only on the search results page)
        at_results = wait_for(browser,'srchResultNotice')

        #The search results page shows the same case link multiple times, with
        #separate rows for each party to the case. The links are all the same; we
        try:
            case_link = browser.find_element_by_css_selector('#grid td a:first-of-type').get_attribute('href')
        #Even though the cases are numbered sequentially, sometimes one isn't in the system...
        #We need to be sure we skip the empty cases, but leave a blank record in our database so we can
        #track the cases we've missed (or the numbers that were skipped--it isn't clear what the situatin
        #is here, yet)
        except:
            case_link = False
        if case_link:
            try:
                browser.get(case_link)
                progress = True
            except:
                progress = False

            if progress:
                #Wait for the case to be loaded (the docket will appear on the page)...
                at_case = wait_for(browser,'docketInfo')

                if at_case:
                    #collect the case header
                    collect_header(browser,case_object)

                    #collect the party information...
                    collect_parties(browser,case_object)

                    #collect any events, dispositions, receipts, and the docket...
                    collect_table(browser,case_object,'event')
                    collect_table(browser,case_object,'disposition')
                    collect_table(browser,case_object,'receipt')
                    collect_table(browser,case_object,'docket')

                    #collect the docket
                    collect_pdfs(browser,case_object)

                    #Add the case object to our collection
                    cases.append(case_object)

#Convert PDF to multi-image TIFF file, save, and then OCR (to hOCR format via tesseract)
def ocr_pdf(file_name):
    with Image(filename=file_name, resolution=300) as image_pdf:
        image_jpeg = image_pdf.convert('jpeg')

        img_list = []
        final_images = []
        count = 0

        for img in image_jpeg.sequence:
            img_page = Image(image=img)
            img_list.append(img_page.make_blob('jpeg'))

            for img in img_list:
                final_images.append(PI.open(io.BytesIO(img)))

        name = file_name.replace('.pdf','')
        file_name = file_name.replace('.pdf','.tif')

        final_images[0].save(name + ".tif",compression="tiff_deflate",save_all=True,append_images=final_images[1:])

    with PyTessBaseAPI() as api:
        api.SetVariable("tessedit_create_hocr", "T")
        api.ProcessPages(name,file_name)

def wait_for(browser,element_id):
    try:
        wait(browser,15).until(EC.presence_of_element_located((By.ID,element_id)))
        return True
    except:
        return False
