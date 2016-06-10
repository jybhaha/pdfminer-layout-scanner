from pdfminer.layout import LTTextBox, LTTextLine, LTFigure, LTImage

class LtsObjectParser:

    def to_bytestring (self, s, enc='utf-8'):
        """Convert the given unicode string to a bytestring, using the standard encoding,
        unless it's already a bytestring"""
        if s:
            if isinstance(s, str):
                return s
            else:
                return s.encode(enc)

    def update_page_text_hash(self, h, lt_obj, pct=0.2):
        """Use the bbox x0,x1 values within pct% to produce lists of associated text within the hash"""

        x0 = lt_obj.bbox[0]
        x1 = lt_obj.bbox[2]

        key_found = False
        for k, v in h.items():
            hash_x0 = k[0]
            if x0 >= (hash_x0 * (1.0 - pct)) and (hash_x0 * (1.0 + pct)) >= x0:
                hash_x1 = k[1]
                if x1 >= (hash_x1 * (1.0 - pct)) and (hash_x1 * (1.0 + pct)) >= x1:
                    # the text inside this LT* object was positioned at the same
                    # width as a prior series of text, so it belongs together
                    key_found = True
                    v.append(self.to_bytestring(lt_obj.get_text()))
                    h[k] = v
        if not key_found:
            # the text, based on width, is a new series,
            # so it gets its own series (entry in the hash)
            h[(x0, x1)] = [self.to_bytestring(lt_obj.get_text())]

        return h

    ###
    ### Extracting Images
    ###

    def write_file(self, folder, filename, filedata, flags='w'):
        """Write the file data to the folder and filename combination
        (flags: 'w' for write text, 'wb' for write binary, use 'a' instead of 'w' for append)"""
        result = False
        if os.path.isdir(folder):
            try:
                file_obj = open(os.path.join(folder, filename), flags)
                file_obj.write(filedata)
                file_obj.close()
                result = True
            except IOError:
                pass
        return result

    def determine_image_type(self, stream_first_4_bytes):
        """Find out the image file type based on the magic number comparison of the first 4 (or 2) bytes"""
        file_type = None
        bytes_as_hex = b2a_hex(stream_first_4_bytes)
        if bytes_as_hex.startswith('ffd8'):
            file_type = '.jpeg'
        elif bytes_as_hex == '89504e47':
            file_type = '.png'
        elif bytes_as_hex == '47494638':
            file_type = '.gif'
        elif bytes_as_hex.startswith('424d'):
            file_type = '.bmp'
        return file_type

    def save_image(self, lt_image, page_number, images_folder):
        """Try to save the image data from this LTImage object, and return the file name, if successful"""
        result = None
        if lt_image.stream:
            file_stream = lt_image.stream.get_rawdata()
            if file_stream:
                file_ext = self.determine_image_type(file_stream[0:4])
                if file_ext:
                    file_name = ''.join([str(page_number), '_', lt_image.name, file_ext])
                    if self.write_file(images_folder, file_name, file_stream, flags='wb'):
                        result = file_name
        return result

class OneColumn (LtsObjectParser):

    def parse_lt_objs (self, lt_objs, page_number, images_folder, text=[]):
        """Iterate through the list of LT* objects and capture the text or image data contained in each"""
        text_content = []

        for lt_obj in lt_objs:
            if isinstance(lt_obj, LTTextBox) or isinstance(lt_obj, LTTextLine):
                # text
                text_content.append(lt_obj.get_text())
            elif isinstance(lt_obj, LTImage):
                # an image, so save it to the designated folder, and note it's place in the text
                saved_file = save_image(lt_obj, page_number, images_folder)
                if saved_file:
                    # use html style <img /> tag to mark the position of the image within the text
                    text_content.append('<img src="'+os.path.join(images_folder, saved_file)+'" />')
                else:
                    print >> sys.stderr, "Error saving image on page", page_number, lt_obj.__repr__
            elif isinstance(lt_obj, LTFigure):
                # LTFigure objects are containers for other LT* objects, so recurse through the children
                text_content.append(self.parse_lt_objs(lt_obj._objs, page_number, images_folder, text_content))

        return '\n'.join(text_content)

class TwoColumns (LtsObjectParser):

    def parse_lt_objs (self, lt_objs, page_number, images_folder, text=[]):
        """Iterate through the list of LT* objects and capture the text or image data contained in each"""
        text_content = []

        page_text = {} # k=(x0, x1) of the bbox, v=list of text strings within that bbox width (physical column)
        for lt_obj in lt_objs:
            if isinstance(lt_obj, LTTextBox) or isinstance(lt_obj, LTTextLine):
                # text, so arrange is logically based on its column width
                page_text = self.update_page_text_hash(page_text, lt_obj)
            elif isinstance(lt_obj, LTImage):
                # an image, so save it to the designated folder, and note its place in the text
                saved_file = save_image(lt_obj, page_number, images_folder)
                if saved_file:
                    # use html style <img /> tag to mark the position of the image within the text
                    text_content.append('<img src="'+os.path.join(images_folder, saved_file)+'" />')
                else:
                    print >> sys.stderr, "error saving image on page", page_number, lt_obj.__repr__
            elif isinstance(lt_obj, LTFigure):
                # LTFigure objects are containers for other LT* objects, so recurse through the children
                text_content.append(self.parse_lt_objs(lt_obj._objs, page_number, images_folder, text_content))

        for k, v in sorted([(key,value) for (key,value) in page_text.items()]):
            # sort the page_text hash by the keys (x0,x1 values of the bbox),
            # which produces a top-down, left-to-right sequence of related columns
            text_content.append('\n'.join(v))

        return '\n'.join(text_content)