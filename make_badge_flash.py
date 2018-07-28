import math
import argparse
import os, os.path

import struct
from intelhex import IntelHex
from PIL import Image

# Returns next position
def put_bytes_at(ih, position, bts):
    for i in range(len(bts)):
        ih[position + i] = bts[i]
    return position + len(bts)
            
def main():
    parser = argparse.ArgumentParser("Create the flash data for a queercon 15 badge.")
    
    parser.add_argument('-o', '--hexpath', action='store', type=str, default='a.bin', help='Output file path')
    parser.add_argument('-b', '--badge-name', action='store', type=str, default='Skippy')
    parser.add_argument('id', type=int, action='store', default=1)
        
    args = parser.parse_args()
        
    flash = IntelHex()
    all_frames = []
    curr_frame_index = 0
    tile_animations = [] # This is a bit sequence
    game_animations = [] # This is a bit sequence (not nested)
    
    # The reserved keyword
    put_bytes_at(flash, 0, [0xAB])
    
    # OK. The badge will handle the main and backup confs.
    # All we need along those lines is to give it the ID.
    put_bytes_at(flash, 0x010000, map(ord, struct.pack('<H', args.id)))
    put_bytes_at(flash, 0x040000, map(ord, struct.pack('<H', args.id)))
    
    # Badge name goes here:
    put_bytes_at(flash, 0x030000, map(ord, struct.pack('11s', args.badge_name)))
    put_bytes_at(flash, 0x060000, map(ord, struct.pack('11s', args.badge_name)))
    
    # TODO: Add ALL the badge names, reading them from a file.
    
    if args.hexpath.endswith('.hex'):
        flash.write_hex_file(args.hexpath)
    else:
        flash.tobinfile(args.hexpath)
    
if __name__ == "__main__":
    main()
