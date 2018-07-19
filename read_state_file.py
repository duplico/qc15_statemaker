from __future__ import print_function

import argparse
import os

import networkx as nx

from qc15_game.qc_state import ActionChoice, QcState
from qc15_game import *

# Get the names of the files in the directory - these are the state names
#   Assign IDs to the names
# Parse each one

# First, some definitions. A state takes a series of input tuples. An input
#  tuple is a unique pairing of (input_type, input_details). Multiple identical
#  input tuples are resolved probabilistically - that is, we determine THAT the
#  tuple will fire, then decide which ACTION CHOICE will fire.
# The (possible 1-length) list of Action Choices is called an Action Set.
# An Action Choice is a list of result tuples. A result tuple is described
#  by its (result_type, result_detail, result_duration) 3-tuple.
# So, to summarize. A state has a list of INPUT TUPLES. Each input tuple has an
#  ACTION SET, which is a set of ACTION CHOICES. Only 1 action choice fires at
#  a time, and when it fires its list of RESULTS will occur.
# A new Action Choice is denoted in the specification by its input tuple.
# The results list (if longer than 1 item) will be denoted by the special
#  CONTD input type.
   
def get_graph(statefile, allow_implicit):
    # Now we're going to build our pretty graph.
    state_graph = nx.MultiDiGraph()
    
    for state in QcState.states_objects:
        # Add all the states (nodes):
        state_graph.add_node(state)
    for state in QcState.states_objects:
        #if state.name in SPECIAL_STATES: continue
        for input_tuple, action_set in state.actionsets.items():
            for action_choice in action_set:
                if action_choice.dest_state == state: continue
                state_graph.add_edge(state, action_choice.dest_state,
                                     object=action_choice,
                                     label=action_choice.label_tuple())
    return state_graph

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
    
    ActionChoice.default_duration = args.default_duration
    QcState.make_states(args.statefile, args.allow_implicit)
    
    
    state_graph = get_graph(args.statefile, args.allow_implicit)
    if args.dotfile:
        nx.drawing.nx_pydot.write_dot(state_graph, args.dotfile)
    
if __name__ == "__main__":
    main()