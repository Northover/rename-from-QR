# Bulk rename image files by scanning for embedded QR metadata

## Requirements
```
aiofiles==0.4.0
Pillow==7.0.0
pyzbar==0.1.8

ZBar system library
```

## Usage
```
usage: rename-from-QR.py [-h] [-a ANGLES [ANGLES ...]] [-m]
                         [-f FILTERS [FILTERS ...]] [-t THREADS]
                         DIRS [DIRS ...]

Rename files based upon their QR codes

positional arguments:
  DIRS                  One or more directories containing images to scan

optional arguments:
  -h, --help            show this help message and exit
  -a ANGLES [ANGLES ...], --angles ANGLES [ANGLES ...]
                        Attempt rescanning images rotated by the supplied
                        degrees
  -m, --monochrome      Load the image as monochrome
  -f FILTERS [FILTERS ...], --filters FILTERS [FILTERS ...]
                        Which image filters to apply
  -t THREADS, --threads THREADS
                        How many threads to use - Defaults to the number of
                        cores on the system
```

## TODO:
1. Add a better Docker image
2. Add a UI
3. Make a more portable package - Windows support is currently poor
4. Rewrite the lot in Rust :)
