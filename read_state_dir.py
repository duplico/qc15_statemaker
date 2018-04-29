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

IGNORE_STATES = ['EXAMPLE_NOTPARSED', 'SHEETNAMES']
VALID_INPUT_TYPES = ['ENTER', 'USER_IN', 'BUTTON', 'NET', 'TIMER', 'TIMER_R',
                     'CONTD']
VALID_RESULT_TYPES = ['TEXT', 'SET_ANIM_TEMP', 'SET_ANIM_BG', 
                      'STATE_TRANSITION', 'OTHER']
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
            self.dest_state = states_objects[state_ids[results_tuple[1]]]
        
        self.results_list.append(results_tuple)
    
    def validate_line(self, action_line, result):
        
        if action_line['Result_type'] not in VALID_RESULT_TYPES:
            self.state.error(
                'Invalid Result_type %s' % action_line['Result_type'],
                action_line
            )
        if self.results_list and self.results_list[-1][0] == 'STATE_TRANSITION':
            self.state.error(
                'STATE_TRANSITION must be last in its action choice.',
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
            if action_line['Result_detail'] not in state_names:
                # We've encountered a state transition to an undefined state.
                s = action_line['Result_detail']
                if self.state.allow_implicit:
                    # Declare it implicitly for development purposes.
                    print '!!! WARNING: Implicit declaration of state %s' % s
                    new_state_id = len(state_names)
                    state_names.append(s)
                    state_ids[s] = new_state_id
                    states_objects.append(QcState(
                        new_state_id,
                        s,
                        self.state.allow_implicit,
                        True
                    ))
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
            self.results_list
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
        print '!!! ERROR while parsing state %s:' % self.name
        print '\t%s' % message
        if action_line:
            print '\tOffending details are: %s' % str(action_line)
        exit(1)
        
    def choice_total(self, input_tuple):
        if input_tuple not in self.actionsets:
            raise Exception('Non-existent input tuple specified')
        
        return sum(ac.choice_share for ac in self.actionsets[input_tuple])
        
        
    def __str__(self):
        rep = '%s\n' % self.name
        rep += '='*len(self.name) + '\n'
        for input_tuple, action_set in self.actionsets.items():
            rep += repr(input_tuple) + ':\n'
            for action_choice in action_set:
                rep += '\t%s\n' % str(action_choice)
        return rep
        
    def __repr__(self):
        return "QcState(%d, %s)" % (
            self.id, 
            self.name, 
            #repr(self.actionset)
        )

def populate_state_lists(statedir, state_names, state_ids, state_paths):
    # Read the names of the files in the directory - these are state names
    # We want these to be case-insensitive, so we're converting them all to
    # upper-case.    
    current_state_id = 0
    
    die_due_to_encoding = dict()
    
    for statefile in map(lambda a: a.upper(), os.listdir(statedir)):
        if not statefile.endswith('.CSV'):
            print '! WARNING:',
            print 'Ignoring %s (non-CSV)' % statefile
            continue
        if len(statefile.split('.')) != 2:
            print '! WARNING:',
            print 'Ignoring %s (Wrong number of dots)' % statefile
            continue
        state_name = statefile.split('.')[0]
        if state_name in IGNORE_STATES:
            print '! WARNING:',
            print 'Ignoring %s (ignore list)' % state_name
            continue
        print current_state_id, state_name
        state_path = os.path.join(statedir, statefile)
        state_names.append(state_name)
        state_paths.append(state_path)
        state_ids[state_name] = current_state_id
        current_state_id += 1
        
        # Check encoding:
        det = UniversalDetector()
        for line in open(state_path):
            det.feed(line)
            if det.done: break
        det.close()
        if det.result['encoding'] != 'ascii':
            die_due_to_encoding[statefile] = det.result['encoding']
    if die_due_to_encoding:
        for statefile, encoding in die_due_to_encoding.items():
            print '!!! ERROR: Non-ASCII encoding %s detected in file %s' % (
                encoding,
                statefile
            )
        exit(1)
        

def read_state_defs(state_paths, allow_implicit):
    for state_id in range(len(state_paths)):
        state_path = state_paths[state_id]
        state_definition = []
        line_number = 0
        
        with open(state_path) as csvfile:
            csvreader = csv.DictReader(csvfile)
            for row in csvreader:
                assert row['Input_type'] in VALID_INPUT_TYPES
                assert row['Result_type'] in VALID_RESULT_TYPES
                state_definition.append(row)
        state = QcState(state_id, state_names[state_id], allow_implicit,
                        definition_list=state_definition)
        states_objects.append(state)
    return states_objects

def get_graph(statedir, allow_implicit):
    global state_names # Mapping of state IDs to names
    global state_ids # Mapping of state names to IDs
    global states_objects # Mapping of state IDs to state objects
    state_paths = [] # Mapping of state IDs to paths
    
    # Get the initial names, IDs, and file paths of all state definitions:
    populate_state_lists(statedir, state_names, state_ids, state_paths)
    
    # Read the state CSV files into a list:
    states_objects = read_state_defs(state_paths, allow_implicit)
    
    # Finally, process each state's definition into the canonical object form:
    for state in states_objects:
        state.process_definition()
    for state in states_objects:
        print state
        
    # Now we're going to build our pretty graph.
    state_graph = nx.MultiDiGraph()
    
    for state in states_objects:
        # Add all the states (nodes):
        state_graph.add_node(state)
    for state in states_objects:
        for input_tuple, action_set in state.actionsets.items():
            for action_choice in action_set:
                state_graph.add_edge(state, action_choice.dest_state,
                                     object=action_choice,
                                     label=action_choice.label_tuple())
    nx.drawing.nx_pydot.write_dot(state_graph, 'out.dot')
    

def main():
    parser = argparse.ArgumentParser("Parse the state data for a qc15 badge.")
    parser.add_argument('--statedir', type=str, default='state_files', 
        help="Directory containing all the states' CSV files.")
    parser.add_argument('--default-duration', type=int, default=5,
        help="The default duration of actions whose durations are unspecified.")
    parser.add_argument('--allow-implicit', action='store_true',
                        help='Allow the implicit declaration of states.')
    
    args = parser.parse_args()
    
    assert os.path.isdir(args.statedir)
    
    global default_duration
    default_duration = args.default_duration
    
    get_graph(args.statedir, args.allow_implicit)
    
if __name__ == "__main__":
    main()