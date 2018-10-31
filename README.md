# dc-court-collector
A tool for turning the District of Columbia's eAccess Court Portal's pages into a collection of data that can be queried and studied.

1) File Structure:

  * There are two files: dc_court_collector.py and subroutines.py. In addition, these files assume a folder called "case_data" present in the same location as the scripts. The "case_data" folder should have a subfolder inside it called "case_documents". (These folders are storing collected data, for the time being--eventually they should be replaced by a database...)

2) Prerequisites:

  * Python3 (Python 3.7 is the version I'm currently running)
  * jenv + java (SDK u8u191)
  * Python packages (installed via pip, ideally):
    - cmd2 [to manage the program shell]
    - pandas [data analysis tool]
    - selenium (automated web browser, for exploring DC eAccess)
      - NOTE: selenium depends on Google Chrome
      - NOTE: selenium depends on your system running a version of chromedriver that will allow it to manipulate Google Chrome: https://github.com/SeleniumHQ/selenium/wiki/ChromeDriver
    - Wand (image manipulation library, for prepping and OCRing PDFs)
      - NOTE: Wand depends on the ImageMagick library; https://www.imagemagick.org/script/index.php
    - PIL (another image library)
      - NOTE: PIP is defunct, so you'll want to install Pillow here instead (see https://stackoverflow.com/questions/20060096/installing-pil-with-pip)
    - tesserocr (for OCRing PDFs)
      - NOTE: Tesserocr depends on Tesseract: https://github.com/tesseract-ocr/
      - NOTE: Tesseract also needs its English-language training materials: See the guide at http://guides.library.illinois.edu/c.php?g=347520&p=4121425

3) Program Routines

  * The main routine is collectCases:
    - Open a Selenium window into the \n DC Court's eAccess page, then provide an abbreviated case reference (e.g., 18LTB12) as a starting point, then the number of cases you want to collect, or another case reference, as an end point. The tool will attempt to collect all of the cases, including any attached documents. When it completes its collection run, it will attempt to OCR any attached documents it found.
    - NOTE: At the moment, collectCases stores its data in temporary json files and the files it downloads in the filesystem. This structure is flexible, but rickety. A next step should be setting up a database to store information in a firmer, more reliable structure. I've held off on creating the database because I want to talk more with DC Bar Foundation about its aims and needs before settling on a database structure.

  * collectCases occasionally runs into trouble when the eAccess portal fails. When this happens, the temporary json files collectCases creates can get orphaned--as can the files it downloads. When this happens, there are two additional routines that consolidate and parse files left over from any incomplete run of collectCases:
    -cleanupData: consolidates the tempoary json files into the "final.json" file (in the root folder) that stores the current final form of the data. YOU CAN ALSO USE cleanupData TO VIEW THE DATA OBJECT FOR A SPECIFIC CASE, AS A SHORTCUT (e.g., cleanupData 18LTB132)
    -cleanupDocs: OCRs any outstanding documents. The routine also deletes any downloaded PDFs that were not properly associated with a case due to an error.

4) Next Steps

  * As mentioned in the "Program Routines" section, an important next step will be moving beyond the JSON/filesystem data storage strategy into an actual database structure. I've held off on creating the database because I want to talk more with DC Bar Foundation about its aims and needs before settling on a database structure.

  * collectCases (and the ocr_pdf subroutine) are written to create HOCR files (https://en.wikipedia.org/wiki/HOCR). Because these files contain text guesses but also layout information, I'm hoping it will be possible to teach the tool to collect information it expects to find in particular sections of a document. This should make collecting data from paper forms more reliable, since we can predict what pieces of information we're looking for in which sections on the document's layout.
    - I got the idea for this approach from JSFenFen's "WhatWordWhere" project (https://github.com/jsfenfen/whatwordwhere), but I've had a lot of trouble so far updating this project to run in Python 3. Getting WhatWordWhere to run so it can work on our HOCR files--or reproducing its method from scratch--is the other major challenge this project needs to overcome right now.
