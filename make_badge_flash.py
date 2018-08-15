"""Tool to assemble statemaker output and ID numbers to a QC15 flash image."""

import math
import argparse
import os, os.path

import struct
from intelhex import IntelHex
from PIL import Image

__author__ = "George Louthan @duplico"
__copyright__ = "(c) 2018, George Louthan"
__license__ = "MIT"
__email__ = "duplico@dupli.co"

# Returns next position
def put_bytes_at(ih, position, bts):
    for i in range(len(bts)):
        ih[position + i] = bts[i]
    return position + len(bts)
            
def main():
    parser = argparse.ArgumentParser("Create the flash data for a queercon 15 badge.")
    
    parser.add_argument('-o', '--hexpath', action='store', type=str, default='a.bin', help='Output file path')
    parser.add_argument('-b', '--badge-name', action='store', type=str, default='Skippy')
    parser.add_argument('game_hex', type=str, action='store')
    parser.add_argument('id', type=int, action='store')
    
    args = parser.parse_args()
        
    flash = IntelHex()

    flash.loadhex(args.game_hex)
    
    # The sentinel word:
    flash.puts(0, '\xab\xba')
    
    # OK. The badge will handle the main and backup confs.
    # All we need along those lines is to give it the ID.
    flash.puts(0x010000, struct.pack('<H', args.id))
    flash.puts(0x040000, struct.pack('<H', args.id))
    
    # Badge name goes here:
    # TODO: get it out of the badge file instead.
    flash.puts(0x030000, struct.pack('11s', args.badge_name))
    flash.puts(0x060000, struct.pack('11s', args.badge_name))
    
    # TODO: Add ALL the badge names, reading them from a file.
    # flash.puts
    
    if args.hexpath.endswith('.hex'):
        flash.write_hex_file(args.hexpath)
    else:
        flash.tobinfile(args.hexpath)
    
if __name__ == "__main__":
    main()
