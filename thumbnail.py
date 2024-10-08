#!/usr/bin/env /Users/robin/Projects/ElegooNeptuneThumbnailPrusaMod/.venv/bin/python3

# Copyright (c) 2023 fifonik
# Copyright (c) 2023 TheJMaster28
# Copyright (c) 2023 Molodos
# Copyright (c) 2023 sigathi
# Copyright (c) 2020 DhanOS
# The ElegooNeptuneThumbnailPrusaMod plugin is released under the terms of the AGPLv3 or higher.


import argparse
import base64
import logging
import platform
import re
import sys

from array import array
from ctypes import *
from io import BytesIO
from os import path, replace

from PIL import Image, ImageOps, ImageDraw,ImageFont

import lib_col_pic

script_dir = path.dirname(sys.argv[0])
log_file = path.join(script_dir, path.splitext(sys.argv[0])[0] + '.log')
logging.basicConfig(level=logging.DEBUG, filename=log_file, filemode="w", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def myround(svalue, divider=1) -> str:
    f = float(svalue) / divider
    if abs(f) < 10:
        return str(round(f, 1));
    else:
        return str(round(f));


def extract_value(line, key) -> str:
    p = line.find(key)
    if p < 0:
        return ''
    pv = p + len(key);
    p2 = line.find(';', pv)
    if p2 >= 0:
        return line[pv:p2].strip()
    else:
        return line[pv:].strip()


class Neptune_Thumbnail:
    def __init__(self, input_file, old_printer=False, image_size=None, debug=False, short_duration_format=False, update_original_image=False, original_image_light_theme=False):
        self.input_file = input_file
        self.debug = debug
        self.filament_cost = None
        self.filament_used_weight = None
        self.filament_used_weight_formatted = None
        self.filament_used_length = None
        self.filament_used_length_formatted = None
        self.header = ''
        self.header_line = None
        self.img_base64_block_len = 78
        self.img_encoded = ''
        self.img_encoded_begin = None
        self.img_encoded_end = None
        self.img_size = image_size
        self.img_type = None
        self.img_type_detected = None
        self.img_width = None
        self.img_height = None
        self.max_height = 0
        self.max_height_formatted = None
        self.original_image_light_theme = original_image_light_theme
        self.print_duration = None
        self.print_duration_formatted = None
        self.print_duration_short_format = short_duration_format
        self.update_original_image = update_original_image
        self.orca_mask = 'Orca-Slicer'
        self.prusa_mask = 'Prusa-Slicer'
        self.run_old_printer = old_printer

        logger.info(f'Input file: {args.input_file}')
        if self.img_size is None:
            logger.info('The first thumbnail from input file larger than 100x100 will be used')
        else:
            logger.info(f'Will try to find thumbnail with specified size: {self.img_size}')
        if self.print_duration_short_format:
            logger.info('Using short pring duration format')
        if self.run_old_printer:
            logger.info('Using older printer settings')
        if self.update_original_image:
            logger.info('Original image will be updated')


    def log_debug(self, str):
        if self.debug:
            logger.debug(str)


    def parse(self):
        self.log_debug('Parsing file')

        img_size_regex = re.compile(r'(?P<size>(?P<width>\d+)x(?P<height>\d+))')
        img_end_token = '; thumbnail end'
        img_size = self.img_size
        with open(self.input_file, 'r', encoding='utf8') as input:
            for index, line in enumerate(input):
                if line.startswith('; generated by '):
                    self.header = line
                    self.header_line = index
                    self.log_debug(f'"generated by" found at line {index}')
                elif 'estimated printing time (normal mode) =' in line:
                    self.print_duration = extract_value(line, 'estimated printing time (normal mode) =')
                    self.log_debug(f'Print duration "{self.print_duration}" found at line {index}')
                elif 'total filament used [g] =' in line:
                    self.filament_used_weight = extract_value(line, 'total filament used [g] =')
                    self.log_debug(f'Filament used [g] "{self.filament_used_weight}" found at line {index}')
                elif 'filament used [mm] =' in line:
                    self.filament_used_length = extract_value(line, 'filament used [mm] =')
                    self.log_debug(f'Filament used [mm] "{self.filament_used_length}" found at line {index}')
                elif 'total filament cost =' in line:
                    self.filament_cost = extract_value(line, 'total filament cost =')
                    self.log_debug(f'Filament cost "{self.filament_cost}" found at line {index}')
                elif line.startswith(';Z:'):
                    value = line.split(':')
                    height = float(value[1].strip())
                    if height > self.max_height:
                        self.max_height = height
                elif line.startswith('; thumbnail') and ' begin' in line:
                    found = False
                    if self.img_size is None:
                        m = img_size_regex.search(line)
                        if m is not None and int(m.group('width')) >= 100 and int(m.group('height')) >= 100:
                            found = True
                            self.img_size = m.group('size')
                    elif f' {self.img_size} ' in line:
                        found = True
                    if found:
                        _ = self.img_size.split('x')
                        self.img_width = int(_[0])
                        self.img_height = int(_[1])
                        self.img_encoded_begin = index
                        if 'thumbnail_JPG' in line:
                            self.img_type = 'JPG'
                            img_end_token = '; thumbnail_JPG end'
                        self.log_debug(f'{self.img_type} thumbnail begin found at line {index}')
                elif self.img_encoded_begin is not None and self.img_encoded_end is None and line.startswith(img_end_token):
                    self.img_encoded_end = index
                    self.log_debug(f'{self.img_type} thumbnail end found at line {index}')
                elif self.img_encoded_begin is not None and self.img_encoded_end is None:
                    self.img_encoded += line.strip('; ')
                if self.print_duration is not None and self.filament_cost is not None and self.filament_used_length is not None and self.filament_used_weight is not None and self.img_encoded_begin is not None and self.img_encoded_end is not None:
                    return

            if img_size is not None:
                # Show error cause by "thumbnail not found" only if size was specified in options
                if self.img_encoded_begin is None:
                    raise Exception(f'Thumbnail begin not found in {self.input_file}')
                if self.img_encoded_begin is not None and self.img_encoded_end is None:
                    raise Exception(f'Thumbnail end not found in {self.input_file}')


    def prepare(self):
        if self.print_duration is not None:
            if self.print_duration_short_format:
                def repl(m):
                    s = m.group(1)
                    if s is None:
                        return ''
                    match m.group(2):
                        case 'd':
                            return s + m.group(2) + 'd '
                        case 's':
                            return ''
                    return ':' + '{:02d}'.format(int(s))
                s = re.sub(r'\s*(\d+)\s*([dhms])', repl, self.print_duration)
                s = s.replace(' :', ' ').strip(': ')
                if ':' not in s:
                    s = '00:' + s
                self.print_duration_formatted = s
            else:
                self.print_duration_formatted = self.print_duration


        if self.filament_used_weight is not None:
            # todo@ find better char and use \uXXXX
            self.filament_used_weight_formatted = myround(self.filament_used_weight) + 'g'

        if self.filament_used_length is not None:
            # todo@ find better char and use \uXXXX
            self.filament_used_length_formatted = myround(self.filament_used_length, 1000) + 'm'

        if self.max_height > 0:
            self.max_height_formatted = '{:.1f}'.format(round(self.max_height, 1)) + 'mm'


    def image_decode(self, text) -> Image:
        """
        Decodes base64 encoded image to QImage
        """
        if not text:
            raise Exception('Thumbnail text is empty')

        self.log_debug('Decoding thumbnail from base64')
        text_bytes = text.encode('ascii')
        decode_data = base64.b64decode(text_bytes)
        image_stream = BytesIO(decode_data)
        img = Image.open(image_stream).convert('RGBA')

        self.img_type_detected = 'PNG'

        return img


    def image_resize(self, img: Image, size) -> Image:
        """
        Resize image
        """
        if img is None:
            raise Exception('No image')

        if img.width == size:
            return Image(img);

        self.log_debug(f'Scaling image to {size}x{size}')
        return ImageOps.scale(img, size/img.width)


    def image_modify(self, img: Image, light_theme: bool=False) -> Image:
        """
        Add texts to image
        """
        if self.print_duration_formatted is None and self.max_height_formatted is None and self.filament_used_weight_formatted is None and self.filament_used_length_formatted is None:
            return img;

        self.log_debug('Adding texts to image')

        img_copy = img.copy()

        draw = ImageDraw.Draw(img_copy)

        font_size = int(img.height / 14);


        draw.font = ImageFont.truetype("Helvetica", font_size)
        draw.fontmode = "L"

        bgcolor = None
        if light_theme:
            color = (0, 0, 0, 255)
            bgcolor = (255, 255, 255, 255)
        else:
            color = (255, 255, 255, 255)
            bgcolor = (0, 0, 0, 128)

        rect_top = [0, 0, img.width, font_size]
        rect_bottom = [0, img.height-font_size, img.width, img.height]
        self.log_debug(rect_bottom)

        draw.rectangle(rect_top, fill=bgcolor, width=0)
        draw.rectangle(rect_bottom, fill=bgcolor, width=0)


        if self.print_duration_formatted is not None:
            draw.text((rect_top[0], rect_top[1]), self.print_duration_formatted, fill=color)
        if self.max_height_formatted is not None:
            length = draw.textlength(self.max_height_formatted)
            draw.text((rect_top[2]-length, rect_top[1]), self.max_height_formatted, fill=color)
        if self.filament_used_weight_formatted is not None:
            draw.text((rect_bottom[0], rect_bottom[1]), self.filament_used_weight_formatted, fill=color)
        if self.filament_used_length_formatted is not None:
            length = draw.textlength(self.filament_used_length_formatted)
            draw.text((rect_bottom[2]-length, rect_bottom[1]), self.filament_used_length_formatted, fill=color)

        if self.debug:
            img_type = self.img_type
            if img_type is None:
                img_type = 'PNG'
            img_copy.save(path.join(script_dir, 'img-' + str(img.width) + 'x' + str(img.height) + '.' + img_type.lower()))

        return img_copy


    def image_encode(self, img: Image, prefix) -> str:
        """
        Encode image for old printers
        """
        if img is None:
            raise Exception('No image')

        self.log_debug(f'Encoding image for old printers ({prefix})')
        result = ''
        width = img.width
        height = img.height
        result += prefix
        datasize = 0
        for i in range(height):
            for j in range(width):
                pixel_color = img.pixelColor(j, i)
                r = pixel_color.red() >> 3
                g = pixel_color.green() >> 2
                b = pixel_color.blue() >> 3
                rgb = (r << 11) | (g << 5) | b
                str_hex = '%x' % rgb
                match len(str_hex):
                    case 3:
                        str_hex = '0' + str_hex[0:3]
                    case 2:
                        str_hex = '00' + str_hex[0:2]
                    case 1:
                        str_hex = '000' + str_hex[0:1]
                if str_hex[2:4] != '':
                    result += str_hex[2:4]
                    datasize += 2
                if str_hex[0:2] != '':
                    result += str_hex[0:2]
                    datasize += 2
                if datasize >= 50:
                    datasize = 0
            result += '\rM10086 ;'
            if i == height - 1:
                result += '\r'
        return result


    def image_encode_new(self, img: Image, prefix) -> str:
        """
        Encode image for new printers
        """
        if img is None:
            raise Exception('No image to encode')

        self.log_debug(f'Encoding image for new printers ({prefix})')

        result   = ''
        width    = img.width
        height   = img.height
        background = Image.new('RGBA', img.size, (46,51,72))
        alpha_composite = Image.alpha_composite(background, img)
        b_image = alpha_composite.resize((width, height))
        pixels = b_image.load()
        img_size = (width, height)
        color16 = array('H')

        try:
            for i in range(height):
                for j in range(width):
                    pixel_color = pixels[j, i]
                    r = pixel_color[0] >> 3
                    g = pixel_color[1] >> 2
                    b = pixel_color[2] >> 3
                    rgb = (r << 11) | (g << 5) | b
                    color16.append(rgb)

            buffer_size       = height * width * 10
            buffer            = bytearray(buffer_size)
            encoded_size      = int(lib_col_pic.ColPic_EncodeStr(color16, width, height, buffer, buffer_size, 1024))

            if encoded_size <= 0:
                raise Exception(f'Nothing encoded')


            data0 = str(buffer).replace('\\x00', '')
            data1 = data0[2:len(data0) - 2]
            each_max = 1024 - 8 - 1
            max_line = int(len(data1) / each_max)
            append_len = each_max - 3 - int(len(data1) % each_max) + 10
            j = 0
            for i in range(len(buffer)):
                if buffer[i] != 0:
                    if j == max_line * each_max:
                        result += '\r;' + prefix + chr(buffer[i])
                    elif j == 0:
                        result += prefix + chr(buffer[i])
                    elif j % each_max == 0:
                        result += '\r' + prefix + chr(buffer[i])
                    else:
                        result += chr(buffer[i])
                    j += 1
            result += '\r;'
            for m in range(append_len):
                result += '0'

            # prefix_len        = len(prefix)
            # max_line_len      = 1024
            # max_line_data_len = max_line_len - prefix_len - 1

            # data              = buffer[:encoded_size]
            # data_len          = len(data)
            # lines_count       = int(data_len / max_line_data_len)
            # append_len        = max_line_data_len - 3 - int(data_len % max_line_data_len)
            #
            # #logger.debug(f'image_encode_new: encoded_size={encoded_size} data_len={data_len} lines_count={lines_count} append_len={append_len}')
            # #logger.debug(f'buffer={str(buffer)}')
            # #logger.debug(f'  data={str(data)}')
            #
            # for i in range(data_len):
            #     if i % max_line_data_len == 0:
            #         if i > 0:
            #             result += '\r'
            #             if i == lines_count * max_line_data_len:
            #                 # last line should be ';;gimage:', instead of ';gimage:'
            #                 result += ';'
            #         result += prefix
            #     result += chr(data[i])
            #
            # result += '\r;' + ('0' * append_len)

        except Exception:
            logger.exception('Failed to encode new thumbnail')

        return result + '\r'


    def image_encode_klipper(self, img: Image, img_type: str, base64_block_len: int) -> str:
        """
        Generate image in original Klipper format (base64 with prefix & suffix)
        """
        result: str = '\n'
        byte_buffer = BytesIO()
        img.save(byte_buffer, img_type)
        base64_str: str = base64.b64encode(byte_buffer.getvalue()).decode('ascii')
        base64_len: int = len(base64_str)
        result += f'; thumbnail begin {img.width}x{img.height} {base64_len}\n'
        pos: int = 0
        while pos < base64_len:
            result += f'; {base64_str[pos:pos+base64_block_len]}\n'
            pos += base64_block_len
        result += f'; thumbnail end\n\n'
        return result


    def run(self):
        """
        Main runner for executable
        """
        self.parse()

        self.prepare()

        if not self.img_encoded:
            logger.info('Thumbnail not found in g-code')
            return;

        self.log_debug('Modifying g-code file')

        img = self.image_decode(self.img_encoded)
        img_200x200 = self.image_modify(self.image_resize(img, 200))
        if self.update_original_image:
            img_klipper = self.image_encode_klipper(self.image_modify(img, self.original_image_light_theme), self.img_type_detected, self.img_base64_block_len)

        header = ''

        # Adding image at the very beginning as some reports that comments before image breaks it on some neptune printers
        if self.run_old_printer:
            header += self.image_encode(self.image_modify(self.image_resize(img, 100)), ';simage:')
            header += self.image_encode(img_200x200, ';gimage:')
        else:
            header += self.image_encode_new(img_200x200, ';gimage:')
            header += self.image_encode_new(self.image_modify(self.image_resize(img, 160)), ';simage:')

        header += ' \n\n; Thumbnail Generated by ElegooNeptuneThumbnailPrusaMod\n'
        # seeing if this works for N4 printer thanks to Molodos: https://github.com/Molodos/ElegooNeptuneThumbnails-Prusa
        header += '; Just mentioning Cura_SteamEngine X.X to trick printer into thinking this is Cura\n\n'

        header += self.header.replace('PrusaSlicer', self.prusa_mask).replace('OrcaSlicer', self.orca_mask)
        header += '\n\n'

        output_file = self.input_file + '.output'
        with open(self.input_file, 'r', encoding='utf8') as input, open(output_file, 'w', encoding='utf8') as output:
            self.log_debug(f'Writing new header with image into file {output_file}')
            output.write(header)
            self.log_debug(f'Copying content from file {self.input_file} to file {output_file}')
            time_elapsed = None
            total_duration = None
            for index, line in enumerate(input):
                if index == self.header_line:
                    continue
                if self.update_original_image:
                    if index > self.img_encoded_begin and index <= self.img_encoded_end:
                        continue
                    if index == self.img_encoded_begin:
                        output.write(img_klipper)
                        continue
                if time_elapsed is not None and line.startswith(';LAYER_CHANGE'):
                    output.write(';TIME_ELAPSED:' + str(time_elapsed) + '\n');
                if line.startswith('M73 P'):
                    # Converting 'M73 P<percentage-completed> R<time-left-in-minutes>' to ';TIME:<print-duration-in-seconds>' + ';TIME_ELAPSED:<time-elapsed-in-seconds>'
                    (percentage, time_to_end) = line[5:].split(' R')
                    t = int(time_to_end) * 60
                    if total_duration is None:
                        total_duration = t
                        output.write(';TIME:' + str(total_duration) + '\n')
                        self.log_debug(f'Progress: {percentage}% complete (total duration: {t} seconds)')
                    else:
                        time_elapsed = total_duration - t
                        self.log_debug(f'Progress: {percentage}% complete, {time_elapsed} seconds passed')
                output.write(line)

        if path.isfile(output_file):
            self.log_debug(f'Renaming file {output_file} to {self.input_file}')
            replace(output_file, self.input_file)
        else:
            raise Exception(f'File {output_file} does not exists')

        logger.info('G-code file modification completed')


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(prog=path.basename(__file__))
        parser.add_argument(
            'input_file',
            metavar='gcode-files',
            type=str,
            help='G-code file to be processed.',
        )
        parser.add_argument(
            '--old_printer',
            help='Run for older Neptune Printers',
            default=False,
            action='store_true',
        )
        parser.add_argument(
            '--image_size',
            default=None,
            help='Size of image to find in G-code file to encode (the first thumbnail will be used if this option is not specified)',
        )
        parser.add_argument(
            '--short_duration_format',
            default=False,
            action='store_true',
            help='Use short print duration format (DDd HH:MM)',
        )
        parser.add_argument(
            '--update_original_image',
            default=True,
            action='store_true',
            help='Inject additional information into original image',
        )
        parser.add_argument(
            '--original_image_light_theme',
            default=False,
            action='store_true',
            help='Original image should be modified for light Klipper theme',
        )
        parser.add_argument(
            '--debug',
            default=False,
            action='store_true',
            help='Output image and write additional info into log file',
        )

        args = parser.parse_args()
        obj = Neptune_Thumbnail(
            args.input_file,
            debug=args.debug,
            image_size=args.image_size,
            old_printer=args.old_printer,
            short_duration_format=args.short_duration_format,
            update_original_image=args.update_original_image,
            original_image_light_theme=args.original_image_light_theme
        )
        obj.run()
    except Exception as ex:
        logger.exception('Error occurred while running application.')





# Python sux. I hate it.
