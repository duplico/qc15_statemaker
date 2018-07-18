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
    parser = argparse.ArgumentParser("Create the flash data for a queercon 14 badge.")
    # ** QC15 LAYOUT
    # ** ===========
    # **
    # ** We're going to use UNIFORM 64 KB BLOCKS.
    # **
    # ** 0x000000 - reserved
    # ** 0x010000 - First ID
    # ** 0x020000 - main config
    # ** 0x030000 - Badge name
    # ** 0x040000 - Second ID copy
    # ** 0x050000 - Backup config
    # ** 0x060000 - Badge name second copy
    # ** 0x070000 - Badge names (11 bytes each) (0x070000 - 0x071356)
    # ** READ NAMES:
    # ** 0x100000 -   0 -  24 (250 bytes)
    # ** 0x110000 -  25 -  49 (250 bytes)
    # ** 0x120000 -  50 -  74 (250 bytes)
    # ** 0x130000 -  75 -  99 (250 bytes)
    # ** 0x140000 - 100 - 124 (250 bytes)
    # ** 0x150000 - 125 - 149 (250 bytes)
    # ** 0x160000 - 150 - 174 (250 bytes)
    # ** 0x170000 - 175 - 199 (250 bytes)
    # ** 0x180000 - 200 - 224 (250 bytes)
    # ** 0x190000 - 225 - 249 (250 bytes)
    # ** 0x1a0000 - 250 - 274 (250 bytes)
    # ** 0x1b0000 - 275 - 299 (250 bytes)
    # ** 0x1c0000 - 300 - 324 (250 bytes)
    # ** 0x1d0000 - 325 - 349 (250 bytes)
    # ** 0x1e0000 - 350 - 374 (250 bytes)
    # ** 0x1f0000 - 375 - 399 (250 bytes)
    # ** 0x200000 - 400 - 424 (250 bytes)
    # ** 0x210000 - 425 - 449 (250 bytes)
    # ** 0x220000 - 450 - 474 (250 bytes)
    # ** ...
    # ** 0x7C0000 - last block
    
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
