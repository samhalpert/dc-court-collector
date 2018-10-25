# dc-court-collector
A tool for turning the District of Columbia's eAccess Court Portal's pages into a collection of data that can be queried and studied.

1) Structure:

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
  - NOTE: PIP is defunct, so you'll want to install Pillow here instead
    (see https://stackoverflow.com/questions/20060096/installing-pil-with-pip)
  - tesserocr (for OCRing PDFs)
  - NOTE: Tesserocr depends on Tesseract: https://github.com/tesseract-ocr/
  - NOTE: Tesseract also needs its English-language training materials:
  See the guide at http://guides.library.illinois.edu/c.php?g=347520&p=4121425
