#!/usr/bin/env python
# encoding: utf-8

""" A script to rename images according to the QR codes contained therein """

# Copyright (c) 2020 Robert Northover

#Permission is hereby granted, free of charge, to any person obtaining a copy of
#this software and associated documentation files (the "Software"), to deal in
#the Software without restriction, including without limitation the rights to
#use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
#of the Software, and to permit persons to whom the Software is furnished to do
#so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.

import aiofiles.os
import argparse
import asyncio
import os

from random import randint, shuffle
from PIL import Image, ImageFilter, ImageOps
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from glob import iglob
from multiprocessing import cpu_count
from pyzbar.pyzbar import decode, ZBarSymbol
from sys import exit

from itertools import product

__author__ = "Robert Northover <rfnorthover@gmail.com>"

# Effective
FILTER = ImageFilter.BLUR
#FILTER = ImageFilter.SMOOTH_MORE
#FILTER = ImageFilter.DETAIL

# Unknown
#FILTER = ImageFilter.SHARPEN

# Ineffective...
#FILTER = ImageFilter.FIND_EDGES

# These filters tend to confuse the scanner...
#FILTER = ImageFilter.EDGE_ENHANCE_MORE
#FILTER = ImageFilter.EDGE_ENHANCE
#FILTER = ImageFilter.CONTOUR

ANGLES = [180, 90, 270, 10, 170, 75, 340] 
#ANGLES = [180, 170, 190, 90, 270, 80, 100, 260, 350, 10]
#ANGLES = [1, 185, 175, 195, 95, 275, 85, 155, 265, 355, 15]
#ANGLES = [i for i in range(1, 360, 37)]
#ANGLES = [i for i in range(8, 360, 90)]
#shuffle(ANGLES)

FILTERS = ["blur", "smooth"]

MAP_FILTERS = dict(
    none=None,
    all="all",
    blur=ImageFilter.BLUR,
    smooth=ImageFilter.SMOOTH_MORE,
    detail=ImageFilter.DETAIL,
    edges=ImageFilter.EDGE_ENHANCE_MORE,
    sharpen=ImageFilter.SHARPEN,
)

MONOCHROME = False

def open_image(image_file: str, rotate: int = 1, filter: str = "blur") -> Image:
    """ Loads the image at :image_file into memory """
    try:
        img = Image.open(image_file)
        #img = ImageOps.autocontrast(img)
        #img = ImageOps.posterize(img, 4)
        #img = ImageOps.crop(img, border=400)

        if rotate:
            # NOTE: the blurring helps Zbar detect a QR code in some cases
            img = img.rotate(rotate)#.filter(FILTER)

        if filter and MAP_FILTERS.get(filter):
            img = img.filter(MAP_FILTERS[filter])

        if MONOCHROME:
            #img = img.convert('1', dither=Image.NONE)
            fn = lambda x : 255 if x > 90 else 0
            img = img.convert('L').point(fn, mode='1')

        #img.show()
        return img
    except Exception as e:
        print(e)

def find_images(directory: str) -> set:
    """ Finds the set of jpg files in the given directory not starting with
    the string 'UMMZI' """
    images = set(iglob(directory + "/**/*.jpg", recursive=True))
    images |= set(iglob(directory + "/**/*.jpeg", recursive=True))
    images |= set(iglob(directory + "/**/image*.jpg", recursive=True))
    images |= set(iglob(directory + "/**/*.JPG", recursive=True))
    images |= set(iglob(directory + "/**/*.JEPG", recursive=True))
    images -= set(iglob(directory + "/**/UMMZI*.jpg", recursive=True))
    images -= set(iglob(directory + "/**/UMMZI*.JPG", recursive=True))

    return images

def _find_duplicates(results: [(str, str)]) -> dict:
    """ Finds all duplicated QR codes given a list of file->QR
    returns a dict of form: {QR: set(filenames containing QR)}
    """
    rev = defaultdict(set)
    for orig, qr in results:
        rev[qr].add(orig)
    return dict(rev)

def _file_mapping(images: [(str, str)]) -> dict:
    """ Produce a dict of form:
        {
            <orig filename>: <QR.jpg>,
            <filename 2>: <QR_copy{n}.jpg> in the case multiple images have the same QR
            ...
        }
    """
    images = _find_duplicates(images)
    mapping = {}

    for qr, files in images.items():
        for i, f in enumerate(files):
            directory = os.path.dirname(f)
            copy = ".jpg" if i == 0 else f"_copy{i}.jpg"
            mapping[f] = os.path.join(directory, f"{qr}{copy}")

    return mapping

def qr_code(filename: str) -> (str, str):
    """ Attempt to retreive the QR from image :filename """

    print(f"Scanning {filename}")
    img = open_image(filename)
    if not img:
        # If the image couldn't be loaded, return the filename twice
        # e.g. oldname == newname
        return filename, os.path.splitext(os.path.basename(filename))[0]

    try:
        # First we try to scan the unadulterated image
        qr = decode(img)
        code = qr[0].data.decode('utf-8')
        if not code.startswith("UMMZI"):
            print(qr[0])
            raise IndexError("Empty code")

        # return the original filename and the extracted QR
        return filename, code
    except IndexError as e:
        # No QR detected, so we try rotating and blurring the image
        for degrees, filters in product(ANGLES, FILTERS):
            print(f".\t", end="")
            try:
                # Rotate image :degrees, blur, and try again
                img = open_image(filename, rotate=degrees, filter=filters)
                qr = decode(img)
                if len(qr) > 0:
                    print(f"Successfully scanned image {filename} with {degrees} degrees of rotation")
                code = qr[0].data.decode('utf-8')
                if not code.startswith("UMMZI"):
                    print(qr[0])
                    raise IndexError("Empty code")
                return filename, code
            except IndexError as err:
                pass

        # Failed to scan, so just return the filename twice
        # We should really return None here and filter it out later...
        return filename, os.path.splitext(os.path.basename(filename))[0]

async def get_qr_codes(executor: ThreadPoolExecutor, directory: str) -> list:
    """For the specified :directory, execute the QR scanner for any detected
    images. These scans are performed asyncronously via the :executor"""

    unscanned = find_images(directory)
    if len(unscanned) == 0:
        exit(f"No unscanned images detected in {directory} - Aborting")

    # Scan concurrently depending on the number of threads specified
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, qr_code, img)
        for img in unscanned 
    ]
    completed, pending = await asyncio.wait(tasks)
    return [qr.result() for qr in completed]


# Asynchronously wrap common os functions
_rename = aiofiles.os.wrap(os.rename)
_exists = aiofiles.os.wrap(os.path.exists)

async def rename_image(old: str, new: str) -> None:
    """ Aynchronously rename file :old to :new if it doesn't exist """
    exists = await _exists(new)
    if not exists:
        print(f"Renaming {old} -> {new}")
        await _rename(old, new)

def main(dirs: [str], workers: int) -> None:
    executor = ThreadPoolExecutor(max_workers=workers)
    loop = asyncio.get_event_loop()
    try:
        for directory in dirs:
            results = loop.run_until_complete(
                get_qr_codes(executor, directory)
            )

            images = _file_mapping(results)
            rename_tasks = asyncio.gather(*(rename_image(old, new) for old, new in images.items()))
            loop.run_until_complete(rename_tasks)
    finally:
        loop.close()


if __name__ == "__main__":
    cores = cpu_count()
    parser = argparse.ArgumentParser(description='Rename files based upon their QR codes')
    parser.add_argument('directories',
                        metavar='DIRS',
                        nargs='+',
                        help='One or more directories containing images to scan')
    parser.add_argument('-a', '--angles',
                        metavar='ANGLES',
                        type=int,
                        default=ANGLES,
                        #default=[180, 90, 270],
                        nargs='+',
                        help='Attempt rescanning images rotated by the supplied degrees')
    parser.add_argument('-m', '--monochrome',
#                        metavar='MONOCHROME',
                        dest='MONOCHROME',
                        action='store_true',
                        help='Load the image as monochrome')
    parser.add_argument('-f', '--filters',
                        metavar='FILTERS',
                        type=str,
                        default=["blur"],
                        choices=MAP_FILTERS.keys(),
                        nargs='+',
                        help='Which image filters to apply')
    parser.add_argument('-t', '--threads',
                        metavar='THREADS',
                        dest='threads',
                        type=int,
                        default=cores,
                        help='How many threads to use - Defaults to the number of cores on the system')
    
    args = parser.parse_args()

    FILTERS = args.filters
    if "all" in args.filters:
        FILTERS = [f for f in MAP_FILTERS.keys() if f not in ["all", "none"]]
        
        
    ANGLES = args.angles
    MONOCHROME = args.MONOCHROME

    main(args.directories, args.threads)

