#!/usr/bin/python

import sys
import os
from binascii import b2a_hex
from pdflayoutscanner.lts_object_parser import *


###
### pdf-miner requirements
###

from pdfminer.pdfparser import PDFParser, PDFDocument, PDFNoOutlines
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams

class LayoutScanner:

    def __init__(self, lst_object_parser_strategy):
        """args:
        -lst_object_parser_strategy: ether 'one_column' or 'two_columns': specifies the shape of the text on in pdf: one or two columns"""
        if lst_object_parser_strategy == 'one_column':
            self.lts_object_parser = OneColumn()
        elif lst_object_parser_strategy == 'two_columns':
            self.lts_object_parser = TwoColumns()
        else:
            raise Exception("lst_object_parser_strategy argument is invalid")

    ###
    ### wrapper
    ###

    def with_pdf (self,pdf_doc, fn, pdf_pwd, *args):
        """Open the pdf document, and apply the function, returning the results"""
        result = None
        try:
            # open the pdf file
            fp = open(pdf_doc, 'rb')
            # create a parser object associated with the file object
            parser = PDFParser(fp)
            # create a PDFDocument object that stores the document structure
            doc = PDFDocument()
            # connect the parser and document objects
            parser.set_document(doc)
            doc.set_parser(parser)
            # supply the password for initialization
            doc.initialize(pdf_pwd)

            if doc.is_extractable:
                # apply the function and return the result
                result = fn(doc, *args)

            # close the pdf file
            fp.close()
        except IOError:
            # the file doesn't exist or similar problem
            raise Exception ('Unable to open file '+pdf_doc)
        return result


    ###
    ### Table of Contents
    ###

    def _parse_toc (self,doc):
        """With an open PDFDocument object, get the table of contents (toc) data
        [this is a higher-order function to be passed to with_pdf()]"""
        toc = []
        try:
            outlines = doc.get_outlines()
            for (level,title,dest,a,se) in outlines:
                toc.append( (level, title) )
        except PDFNoOutlines:
            pass
        return toc

    def get_toc (self,pdf_doc, pdf_pwd=''):
        """Return the table of contents (toc), if any, for this pdf file"""
        return self.with_pdf(pdf_doc, self._parse_toc, pdf_pwd)

    ###
    ### Processing Pages
    ###

    def _parse_pages (self,doc, images_folder):
        """With an open PDFDocument object, get the pages, parse each one, and return the entire text
        [this is a higher-order function to be passed to with_pdf()]"""
        rsrcmgr = PDFResourceManager()
        laparams = LAParams()
        device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)

        text_content = []
        for i, page in enumerate(doc.get_pages()):
            interpreter.process_page(page)
            # receive the LTPage object for this page
            layout = device.get_result()
            # layout is an LTPage object which may contain child objects like LTTextBox, LTFigure, LTImage, etc.
            text_content.append(self.lts_object_parser.parse_lt_objs(layout._objs, (i+1), images_folder))

        return text_content

    def get_pages (self,pdf_doc, pdf_pwd='', images_folder='/tmp'):
        """Process each of the pages in this pdf file and print the entire text to stdout"""
        return '\n\n'.join(self.with_pdf(pdf_doc, self._parse_pages, pdf_pwd, *tuple([images_folder])))
