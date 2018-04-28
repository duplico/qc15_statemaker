import argparse
import os

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
#  ACTION SET, which is a list of ACTION CHOICES. Only 1 action choice fires at
#  a time, and when it fires its list of RESULTS will occur.
# A new Action Choice is denoted in the specification by its input tuple.
# The results list (if longer than 1 item) will be denoted by the special
#  CONTD input type.

class ActionChoice(object):
    def __init__(self, choice_share):
        self.results_list = []
        self.choice_share = int(choice_share) if choice_share else 1
        
    def add_results_line(self, action_line):
        results_tuple = (
            action_line[2], 
            action_line[3], 
            action_line[4] if action_line[4] else default_duration
        )
        
        assert action_line[2] in VALID_RESULT_TYPES
        
        self.results_list.append(results_tuple)
    
    def __repr__(self):
        return str(self.results_list)
        
class QcState(object):
    def __init__(self, id, name):
        self.name = name
        self.id = id
        self.actionset = dict()
        self.working_input_tuple = None
        
    def add_action_line(self, action_line):
        input_tuple = (action_line[0], action_line[1])
        if input_tuple[0] == 'CONTD':
            # We're going to be appending this to the results list of the
            #  working action choice.
            assert self.working_input_tuple
            # The working Action Choice is the latest in the action set
            #  indexed by the working input tuple.
            working_action_choice = self.actionset[self.working_input_tuple][-1]
            working_action_choice.add_results_line(action_line)
        else:
            # This is its own input tuple. We will definitely be creating a new
            #  Action Choice, which will either be appended to an existing
            #  Action Set or be the first element of a new Action Set.
            if input_tuple not in self.actionset:
                # We must create a new Action Set.
                self.actionset[input_tuple] = []
            # Append this Action Choice to the Action Set:
            new_action_choice = ActionChoice(action_line[5])
            new_action_choice.add_results_line(action_line)
            self.actionset[input_tuple].append(new_action_choice)
            
            # Update the working input tuple.
            self.working_input_tuple = input_tuple
            
    def __repr__(self):
        return "QcState(%d, %s, %s)" % (
            self.id, 
            self.name, 
            repr(self.actionset)
        )

IGNORE_STATES = ['EXAMPLE_NOTPARSED', 'SHEETNAMES']
VALID_INPUT_TYPES = ['ENTER', 'USER_IN', 'BUTTON', 'NET', 'TIMER', 'TIMER_R',
                     'CONTD']
VALID_RESULT_TYPES = ['TEXT', 'SET_ANIM_TEMP', 'SET_ANIM_BG', 
                      'STATE_TRANSITION', 'OTHER']
default_duration = 5
                     
def main():
    parser = argparse.ArgumentParser("Parse the state data for a qc15 badge.")
    parser.add_argument('--statedir', type=str, default='state_files', 
        help="Directory containing all the states' CSV files.")
    parser.add_argument('--default-duration', type=int, default=5,
        help="The default duration of actions whose durations are unspecified.")
    
    args = parser.parse_args()
    
    assert os.path.isdir(args.statedir)
    
    global default_duration
    default_duration = args.default_duration
    
    current_state_id = 0 # Running counter
    state_names = [] # Mapping of state IDs to names
    state_ids = dict() # Mapping of state names to IDs
    state_paths = [] # Mapping of state IDs to paths
    state_definitions = [] # Mapping of state IDs to state definitions
    states_objects = []
    
    # Read the names of the files in the directory - these are state names
    # We want these to be case-insensitive, so we're converting them all to
    # upper-case.
    for statefile in map(lambda a: a.upper(), os.listdir(args.statedir)):
        if not statefile.endswith('.CSV'):
            print 'Ign %s (non-CSV)' % statefile
            continue
        if len(statefile.split('.')) != 2:
            print 'Ign %s (Wrong number of dots)' % statefile
            continue
        state_name = statefile.split('.')[0]
        if state_name in IGNORE_STATES:
            print 'Ign %s (ignore list)' % state_name
            continue
        print current_state_id, state_name
        state_path = os.path.join(args.statedir, statefile)
        state_names.append(state_name)
        state_paths.append(state_path)
        state_ids[state_name] = current_state_id
        current_state_id += 1
        
    current_state_id = 0
    for state_path in state_paths:
        state_definition = []
        line_number = 0
        for line in open(state_path):
            line = line.strip()
            if line_number == 0:
                line_number += 1
                continue # Ignore headers
                
            line_elements = line.split(',')
            el_len = len(line_elements)
            # Normalize the length of each action specification to 7:
            # (Input_type, Input_detail, Result_type, Result_detail,
            #  Result_duration, Choice_share, Comment)
            while el_len < 7:
                line_elements.append('')
                el_len+=1
            assert line_elements[0] in VALID_INPUT_TYPES
            assert line_elements[2] in VALID_RESULT_TYPES
            state_definition.append(line_elements)
        state_definitions.append(state_definition)
    
    for state_id in range(len(state_names)):
        # Now that we've read everything, it's time to process each state's
        #  definition and start building our state machine.
        state = QcState(state_id, state_names[state_id])
        for line in state_definitions[state_id]:
            state.add_action_line(line)
        states_objects.append(state)
        print state
    
    
if __name__ == "__main__":
    main()