from __future__ import print_function

import argparse
import os
import csv

import networkx as nx
from chardet.universaldetector import UniversalDetector

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

REQUIRED_HEADINGS = ['Input_type', 'Input_detail', 'Choice_share', 
                     'Result_duration', 'Result_type', 'Result_detail']

IGNORE_STATES = ['EXAMPLE_NOTPARSED', 'SHEETNAMES']
VALID_INPUT_TYPES = ['ENTER', 'USER_IN', 'BUTTON', 'NET', 'TIMER', 'TIMER_R',
                     'CONTD']
IGNORE_INPUT_TYPES = ['', 'COMMENT', 'ACTIONS']
VALID_RESULT_TYPES = ['TEXT', 'SET_ANIM_TEMP', 'SET_ANIM_BG', 
                      'STATE_TRANSITION', 'OTHER', 'CLOSE', 'POP']
RESERVED_STATES = ['POP', 'POST']
SPECIAL_STATES = ['POP', 'GLOBAL']
default_duration = 5

state_names = [] # Mapping of state IDs to names
state_ids = dict() # Mapping of state names to IDs
states_objects = [] # Mapping of state IDs to state objects

class ActionChoice(object):
    def __init__(self, choice_share, state, input_tuple):
        self.results_list = []
        self.choice_share = int(choice_share) if choice_share else 1
        self.state = state
        self.dest_state = self.state
        self.input_tuple = input_tuple
        
    def add_results_line(self, action_line):
        results_tuple = (
            action_line['Result_type'], 
            action_line['Result_detail'],
            action_line['Result_duration'] if action_line['Result_duration'] 
                                         else default_duration
        )
        
        # Validate the new result tuple before appending it to our list:
        self.validate_line(action_line, results_tuple)
        
        if results_tuple[0] == 'STATE_TRANSITION':
            if self.dest_state != self.state:
                self.state.error(
                    'Duplicate STATE_TRANSITIONs are not allowed.',
                    action_line
                )
            print(results_tuple)
            print(state_ids)
            print(states_objects)
            self.dest_state = states_objects[state_ids[results_tuple[1].upper()]]
        
        self.results_list.append(results_tuple)
    
    def validate_line(self, action_line, result):
        
        if action_line['Result_type'] not in VALID_RESULT_TYPES:
            self.state.error(
                'Invalid Result_type %s' % action_line['Result_type'],
                action_line
            )
        if self.results_list and self.results_list[-1][0] == 'STATE_TRANSITION':
            self.state.error(
                'STATE_TRANSITION must be last in its action series.',
                action_line
            )
        
        if action_line['Result_type'] == 'TEXT':
            # Check that it's a valid string
            # TODO: Check the character set against our charset for the
            #       LED display.
            pass
        elif action_line['Result_type'] == 'SET_ANIM_TEMP' or \
         action_line['Result_type'] == 'SET_ANIM_BG':
            # Check that it's a valid string.
            # TODO: We'll be building a master list of these.
            pass
        elif action_line['Result_type'] == 'STATE_TRANSITION':
            # Check that it's a valid state.
            if action_line['Result_detail'].upper() not in state_names:
                # We've encountered a state transition to an undefined state.
                s = action_line['Result_detail'].upper()
                if self.state.allow_implicit:
                    # Declare it implicitly for development purposes.
                    print('! WARNING: Implicit declaration of state %s' % s)
                    print("  This is probably NOT what you want to do for the"\
                    " production badge.")
                    
                    imp_definition_list = [
                        {'Input_type': 'ENTER', 'Input_detail': '',
                         'Result_type': 'TEXT', 'Result_detail': s,
                         'Result_duration': '', 'Choice_share': ''},
                        {'Input_type': 'CONTD', 'Input_detail': '',
                         'Result_type': 'STATE_TRANSITION',
                         'Result_detail': 'POP', 'Result_duration': '',
                         'Choice_share': ''},
                    ]
                    
                    new_state_id = len(state_names)
                    state_names.append(s)
                    state_ids[s] = new_state_id
                    new_state = QcState(new_state_id, s,
                                        self.state.allow_implicit, True,
                                        imp_definition_list)
                    #new_state.process_definition()
                    states_objects.append(new_state)
                else:
                    # Raise an error, as this is a problem for production.
                    self.state.error(
                        'Transition to nonexistent state %s' % s,
                        action_line
                    )
            pass
        elif action_line['Result_type'] == 'OTHER':
            # TODO: Ultimately we'll have a list of these.
            pass
    
    def label_tuple(self):
        return (
            self.input_tuple,
            '%d/%d' % (self.choice_share,
                       self.state.choice_total(self.input_tuple)),
            #self.results_list
        )
    
    def __repr__(self):
        return 'ActionChoice(%d, %s)' % (self.choice_share, repr(self.results_list))
    
    def __str__(self):
        return 'CHOICE %d/%d: %s -> %s' % (
            self.choice_share,
            self.state.choice_total(self.input_tuple),
            repr(self.results_list),
            'self' if self.dest_state == self.state else self.dest_state.name
            )
        
class QcState(object):
    pop_state_id = None
    def __init__(self, id, name, allow_implicit, implicit=False,
                 definition_list=[]):
        self.name = name
        self.id = id
        self.actionsets = dict()
        self.working_input_tuple = None
        self.allow_implicit=allow_implicit
        self.implicit=implicit
        self.definition_list = definition_list
        
    def process_definition(self):
        for action_line in self.definition_list:
            self.add_action_line(action_line)
        
    def add_action_line(self, action_line):
        input_tuple = (
            action_line['Input_type'],
            action_line['Input_detail']
        )
        
        if input_tuple[0] == 'CONTD':
            # TODO: results lists are now called "action series"
            # We're going to be appending this to the results list of the
            #  working action choice.
            if not self.working_input_tuple:
                self.error(
                    'CONTD Input_type without preceding basic Input_type.'
                )
                      
            working_action_choice = self.actionsets[self.working_input_tuple][-1]
        else:
            # This is an explicit input tuple (not a continuation or the last),
            # so we will definitely be creating a new Action Choice.
            working_action_choice = ActionChoice(action_line['Choice_share'],
                                                 self,
                                                 input_tuple)
            # This will also become the current working input tuple:
            self.working_input_tuple = input_tuple
            # We may also need to create an Action Set for it; if not, we'll
            #  add it to the appropriate existing Action Set.
            if input_tuple not in self.actionsets:
                self.actionsets[input_tuple] = []
            self.actionsets[input_tuple].append(working_action_choice)
            
        working_action_choice.add_results_line(action_line)
            
    def error(self, message, action_line=None):
        print('FATAL while parsing state %s:' % self.name)
        print('\t%s' % message)
        if action_line:
            print('\tOffending details are: %s' % str(action_line))
        exit(1)
        
    def choice_total(self, input_tuple):
        if input_tuple not in self.actionsets:
            raise Exception('Non-existent input tuple specified')
        
        return sum(ac.choice_share for ac in self.actionsets[input_tuple])
            
    def __str__(self):
        out_str = '%d %s' % (self.id, self.name)
        for input_tuple, action_choices in self.actionsets.items():
            # if input_tuple[0] == 'ENTER': continue
            for action_choice in action_choices:
                if action_choice.dest_state != self: continue
                out_str += '\n%s("%s")@%s' % (
                    input_tuple[0],
                    input_tuple[1],
                    action_choice.label_tuple()[1]
                )
        return out_str
        
    def __repr__(self):
        return "QcState(%d, %s)" % (
            self.id, 
            self.name, 
            #repr(self.actionset)
        )

def read_state_defs(statefile, allow_implicit):
    st_objects = []
    state_definition = []
    curr_state_id = 0 # 0 is the special POST state
    curr_state_name = None
    row_number = 1
    with open(statefile) as csvfile:
        csvreader = csv.DictReader(csvfile)
        
        for required_heading in REQUIRED_HEADINGS:
            if required_heading not in csvreader.fieldnames:
                print("FATAL: %s:%d" % (statefile, 1))
                print(" Required heading '%s' not found." % required_heading)
                exit(1)
                
        for row in csvreader:
            row_number += 1
            if row['Input_type'] in IGNORE_INPUT_TYPES:
                continue # Skip blank lines, or ones that start with COMMENT or ACTIONS
            if curr_state_id == 0 and row['Input_type'] != 'START_STATE':
                print("FATAL: %s:%d" % (statefile, row_number))
                print(','.join(row.values()))
                print("^~~~~~~ Input type not allowed without STATE_START first")
                exit(1)
            if row['Input_type'] == 'START_STATE':
                # New state.
                if curr_state_id:
                    # Save the current state.                    
                    state_names.append(curr_state_name)
                    state_ids[curr_state_name] = curr_state_id
                    state = QcState(curr_state_id, curr_state_name, allow_implicit,
                                    definition_list=state_definition)
                    st_objects.append(state)
                state_definition = []
                curr_state_id += 1
                curr_state_name = row['Input_detail'].upper()
                if curr_state_name in state_names:
                    print("FATAL: %s:%d" % (statefile, row_number))
                    print(','.join(row.values()))
                    print((" "*(len(row['Input_type'])+2)) + \
                          "^~~~~~~ Duplicate state definition")
                    exit(1)
                continue
            if row['Input_type'] not in VALID_INPUT_TYPES:
                print("FATAL: %s:%d" % (statefile, row_number))
                print(','.join(row.values()))
                print("^~~~~~~ Unknown input type '%s'" % row['Input_type'])
                exit(1)
            if row['Result_type'] not in VALID_RESULT_TYPES:
                    print("FATAL: %s:%d" % (statefile, row_number))
                    print(','.join(row.values()))
                    print((" "*(len(row['Input_type'])+2)) + \
                          "^~~~~~~ Unknown result type '%s'" % str(row['Result_type']))
                    exit(1)
            state_definition.append(row)
        
        # Save the final state:
        if curr_state_id:
            # Save the current state.                    
            state_names.append(curr_state_name)
            state_ids[curr_state_name] = curr_state_id
            state = QcState(curr_state_id, curr_state_name, allow_implicit,
                            definition_list=state_definition)
            st_objects.append(state)
    return st_objects

def mk_post():
    post_definition_list = [
        {'Input_type': 'ENTER', 'Input_detail': '', 'Result_type': 'OTHER',
         'Result_detail': 'POST', 'Result_duration': '', 'Choice_share': ''},
        {'Input_type': 'CONTD', 'Input_detail': '',
         'Result_type': 'STATE_TRANSITION', 'Result_detail': 'FIRSTBOOT',
         'Result_duration': '', 'Choice_share': ''},
    ]
    return QcState(0, 'POST', False, definition_list=post_definition_list)

def get_graph(statefile, allow_implicit):
    global state_names # Mapping of state IDs to names
    global state_ids # Mapping of state names to IDs
    global states_objects # Mapping of state IDs to state objects
    
    # Create the initial POST state, to start with:
    post_state = mk_post()
    state_names.append('POST')
    state_ids['POST'] = 0
    states_objects.append(post_state)
    
    # Validate the statefile:
    #  Must end with .csv:
    if not statefile.upper().endswith('.CSV'):
        print("ERROR: statefile is non-CSV")
        exit(1)
    #  Must be ASCII-encoded
    det = UniversalDetector()
    for line in open(statefile):
        det.feed(line)
        if det.done: break
    det.close()
    if det.result['encoding'] != 'ascii':
        print("ERROR: Non-ASCII encoding %s detected" % det.result['encoding'])
        exit(1)
    
    # Now actually read the state file:    
    states_objects += read_state_defs(statefile, allow_implicit)
    
    # Finally, process each state's definition into the canonical object form:
    for state in states_objects:
        state.process_definition()
    # Now we're going to build our pretty graph.
    state_graph = nx.MultiDiGraph()
    
    for state in states_objects:
        # Add all the states (nodes):
        state_graph.add_node(state)
    for state in states_objects:
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
    
    args = parser.parse_args()
    
    assert os.path.isfile(args.statefile)
    
    global default_duration
    default_duration = args.default_duration
    
    state_graph = get_graph(args.statefile, args.allow_implicit)
    nx.drawing.nx_pydot.write_dot(state_graph, 'out.dot')
    
if __name__ == "__main__":
    main()