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

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter


script_dir = path.dirname(sys.argv[0])
log_file = path.join(script_dir, path.splitext(sys.argv[0])[0] + '.log')
logging.basicConfig(level=logging.DEBUG, filename=log_file, filemode="w", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


app = QGuiApplication(sys.argv)


class Neptune_Thumbnail:
    def __init__(self, input_file, old_printer=False, image_size=None, debug=False, short_duration_format=False):
        self.input_file = input_file
        self.debug = debug
        self.filament_cost = None
        self.filament_used_formatted = None
        self.filament_used_weight = None
        self.filament_used_weight_formatted = None
        self.filament_used_length = None
        self.filament_used_length_formatted = None
        self.header = ''
        self.header_line = None
        self.img_encoded = ''
        self.img_encoded_begin = None
        self.img_encoded_end = None
        self.img_size = image_size
        self.img_type = 'PNG'
        self.img_width = None
        self.img_height = None
        self.max_height = 0
        self.print_duration = None
        self.print_duration_formatted = None
        self.print_duration_short_format = short_duration_format
        self.prusa_mask = 'Prusa-Slicer'
        self.run_old_printer = old_printer

        logger.info(f'Input file: {args.input_file}')
        if self.img_size is None:
            logger.info('The first thumbnail from input file larger than 100x100 will be used')
        else:
            logger.info(f'Will try to find thumbnail with specified size: {self.img_size}')
        if self.run_old_printer:
            logger.info('Using older printer settings')
        if self.print_duration_short_format:
            logger.info('Using short pring duration format')


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
                    self.log_debug(f'PrusaSlicer header found at line {index}')
                elif line.startswith('; estimated printing time (normal mode) ='):
                    value = line.split('=')
                    self.print_duration = value[1].strip()
                    self.log_debug(f'Print duration "{self.print_duration}" found at line {index}')
                elif line.startswith('; total filament used [g] ='):
                    value = line.split('=')
                    self.filament_used_weight = value[1].strip()
                    self.log_debug(f'Filament used [g] "{self.filament_used_weight}" found at line {index}')
                elif line.startswith('; filament used [mm] ='):
                    value = line.split('=')
                    self.filament_used_length = value[1].strip()
                    self.log_debug(f'Filament used [mm] "{self.filament_used_length}" found at line {index}')
                elif line.startswith('; total filament cost ='):
                    value = line.split('=')
                    self.filament_cost = value[1].strip()
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
            if self.print_duration:
                def repl(m):
                    s = m.group(1)
                    if s is None:
                        return ''
                    match m.group(2):
                        case 'd':
                            return s + m.group(2) + ' '
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


        filament_used = []
        if self.filament_used_weight is not None:
            self.filament_used_weight_formatted = str(round(float(self.filament_used_weight))) + 'g'
            filament_used.append(self.filament_used_weight_formatted)

        if self.filament_used_length is not None:
            self.filament_used_length_formatted = str(round(float(self.filament_used_length) / 1000)) + 'm'
            filament_used.append(self.filament_used_length_formatted)

        if filament_used:
            self.filament_used_formatted = ', '.join(filament_used)

        if self.max_height > 0:
            self.max_height_formatted = '{:d}'.format(round(self.max_height)) + 'mm'


    def image_decode(self, text) -> QImage:
        """
        Decodes base64 encode image to QImage
        """
        if not text:
            raise Exception('Thumbnail text is empty')

        self.log_debug('Decoding thumbnail from base64')
        text_bytes = text.encode('ascii')
        decode_data = base64.b64decode(text_bytes)
        image_stream = BytesIO(decode_data)
        img: QImage = QImage.fromData(image_stream.getvalue())

        if img.format() != QImage.Format.Format_ARGB32:
            img = img.convertToFormat(QImage.Format.Format_ARGB32)

        return img


    def image_resize(self, img: QImage, width, height) -> QImage:
        """
        Resize image
        """
        if img is None:
            raise Exception('No image')

        img_size = img.size()
        if img_size.width() == width and img_size.height() == height:
            return QImage(img);

        self.log_debug(f'Scaling image to {width}x{height}')
        return img.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio)


    def image_modify(self, img: QImage) -> QImage:
        """
        Add texts to image
        """
        if self.print_duration_formatted is None and self.filament_used_formatted is None:
            return img;

        self.log_debug('Adding texts to image')

        img_size = img.size()
        font_size = int(img_size.width() / 14);

        rect_top = QRect(3, 1, img_size.width() - 6, int(img_size.height() / 2) - 1)
        rect_bottom = QRect(3, int(img_size.height() / 2), img_size.width() - 6, int(img_size.height() / 2) - 1)

        font = QFont('Arial', font_size)
        font.setStyleHint(QFont.StyleHint.AnyStyle, QFont.StyleStrategy.ForceOutline)

        painter = QPainter()
        painter.begin(img)

        painter.setFont(font)
        painter.setPen(QColor(Qt.GlobalColor.white))

        if self.print_duration_formatted is not None:
            painter.drawText(rect_top, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.print_duration_formatted)

        if self.max_height_formatted is not None:
            painter.drawText(rect_top, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, self.max_height_formatted)

        if self.filament_used_formatted is not None:
            painter.drawText(rect_bottom, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, self.filament_used_formatted)

        painter.end()

        if self.debug:
            img.save(path.join(script_dir, 'img-' + str(img_size.width()) + 'x' + str(img_size.height()) + '.' + self.img_type.lower()))

        return img


    def image_encode(self, img: QImage, prefix) -> str:
        """
        Encode image for old printers
        """
        if img is None:
            raise Exception('No image')

        self.log_debug(f'Encoding image for old printers ({prefix})')
        result = ''
        img_size = img.size()
        width = img_size.width()
        height = img_size.height()
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


    def image_encode_new(self, img: QImage, prefix) -> str:
        """
        Encode image for new printers
        """
        if img is None:
            raise Exception('No image')

        self.log_debug(f'Encoding image for new printers ({prefix})')
        system = platform.system()
        if system == 'Darwin':
            dll_path = path.join(path.dirname(__file__), 'libColPic.dylib')
            p_dll = CDLL(dll_path)
        elif system == 'Linux':
            dll_path = path.join(path.dirname(__file__), 'libColPic.so')
            p_dll = CDLL(dll_path)
        else:
            dll_path = path.join(path.dirname(__file__), 'ColPic_X64.dll')
            p_dll = CDLL(dll_path)

        self.log_debug(f'Using {system} dll: {dll_path}')

        result = ''
        img_size = img.size()
        width = img_size.width()
        height = img_size.height()
        pixels = width * height
        color16 = array('H')
        try:
            for i in range(height):
                for j in range(width):
                    pixel_color = img.pixelColor(j, i)
                    r = pixel_color.red() >> 3
                    g = pixel_color.green() >> 2
                    b = pixel_color.blue() >> 3
                    rgb = (r << 11) | (g << 5) | b
                    color16.append(rgb)

            # int ColPic_EncodeStr(U16* fromcolor16, int picw, int pich, U8* outputdata, int outputmaxtsize, int colorsmax);
            fromcolor16 = color16.tobytes()
            outputdata = array('B', [0] * pixels).tobytes()
            resultInt = p_dll.ColPic_EncodeStr(
                fromcolor16,
                height,
                width,
                outputdata,
                pixels,
                1024,
            )

            data0 = str(outputdata).replace('\\x00', '')
            data1 = data0[2 : len(data0) - 2]
            eachMax = 1024 - 8 - 1
            maxline = int(len(data1) / eachMax)
            appendlen = eachMax - 3 - int(len(data1) % eachMax)

            for i in range(len(data1)):
                if i == maxline * eachMax:
                    result += '\r;' + prefix + data1[i]
                elif i == 0:
                    result += prefix + data1[i]
                elif i % eachMax == 0:
                    result += '\r' + prefix + data1[i]
                else:
                    result += data1[i]
            result += '\r;'
            for j in range(appendlen):
                result += '0'

        except Exception:
            logger.exception('Failed to prase new thumbnail screenshot')

        return result + '\r'


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

        # seeing if this works for N4 printer thanks to Molodos: https://github.com/Molodos/ElegooNeptuneThumbnails-Prusa
        header = self.header.replace('PrusaSlicer', self.prusa_mask)
        header += f'\r; Cura_SteamEngine X.X to trick printer into thinking this is Cura\r'

        img = self.image_decode(self.img_encoded)

        img_200x200 = self.image_modify(self.image_resize(img, 200, 200))
        img_160x160 = self.image_modify(self.image_resize(img, 160, 160))

        if self.run_old_printer:
            header += self.image_encode(img_200x200, ';gimage:')
            header += self.image_encode(img_160x160, ';simage:')
        else:
            header += self.image_encode_new(img_200x200, ';gimage:')
            header += self.image_encode_new(img_160x160, ';simage:')

        header += '\r; Thumbnail Generated by ElegooNeptuneThumbnailPrusaMod\r\r'

        output_file = self.input_file + '.output'
        with open(self.input_file, 'r', encoding='utf8') as input, open(output_file, 'w', encoding='utf8') as output:
            self.log_debug(f'Writing new header with image into file {output_file}')
            output.write(header)
            self.log_debug(f'Copying content from file {self.input_file} to file {output_file}')
            time = None
            time_code = ';TIME:'
            for index, line in enumerate(input):
                if index == self.header_line:
                    continue
                output.write(line)
                if line.startswith('M73 P'):
                    # Converting 'M73 P<percentage-completed> R<time-left-in-minutes>' to ';TIME:<print-duration-in-seconds>' + ';TIME_ELAPSED:<time-elapsed-in-seconds>'
                    (percentage, time_to_end) = line[5:].split(' R')
                    t = int(time_to_end) * 60
                    if time is not None:
                        t = time - t
                    self.log_debug(f'Progress: {percentage}% complete, {t} seconds passed')
                    output.write(time_code + str(t) + '\r');
                    if time is None:
                        time_code = ';TIME_ELAPSED:'
                        time = t;

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
            '--debug',
            default=False,
            action='store_true',
            help='Output image and write additional info into log file',
        )

        args = parser.parse_args()
        obj = Neptune_Thumbnail(args.input_file, old_printer=args.old_printer, image_size=args.image_size, debug=args.debug, short_duration_format=args.short_duration_format)
        obj.run()
    except Exception as ex:
        logger.exception('Error occurred while running application.')
