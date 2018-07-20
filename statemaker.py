from __future__ import print_function

import argparse
import os

import networkx as nx

from qc15_game.game_state import *
from qc15_game import *

def main():
    parser = argparse.ArgumentParser("Parse the state data for a qc15 badge.")
    parser.add_argument('--statefile', type=str, default='state_file.csv', 
        help="Path to CSV file containing all the states for the game.")        
    parser.add_argument('--default-duration', type=int, default=5,
        help="The default duration of actions whose durations are unspecified.")
    parser.add_argument('--allow-implicit', action='store_true',
                        help='Allow the implicit declaration of states. This'\
                             ' is almost certainly NOT what you want to do for'\
                             " the production badge, but during development it"\
                             " might be useful. This will generate a dead-end"\
                             " state that automatically displays its name and"\
                             " returns to the previous state after the default"\
                             " delay.")
    parser.add_argument('-d', '--dotfile', type=str, default='', 
        help="Path to GraphViz dot file to generate.")  
    
    args = parser.parse_args()
    if not os.path.isfile(args.statefile):
        print("FATAL: %s" % (args.statefile))
        print(" File not found.")
        exit(1)
    
    # TODO: default duration
    # TODO: allow implicit
    
    state_graph = read_state_data(args.statefile, args.allow_implicit)
    
    if args.dotfile:
        nx.drawing.nx_pydot.write_dot(state_graph, args.dotfile)
    
if __name__ == "__main__":
    main()