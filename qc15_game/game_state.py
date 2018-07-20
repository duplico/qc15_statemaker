from __future__ import print_function

import csv

import networkx as nx
from chardet.universaldetector import UniversalDetector

from qc15_game import *

all_actions = []
all_states = []
state_name_ids = dict()

class GameAction(object):
    def __init__(self, input_tuple, state_name, prev_action, prev_choice,
                 action_type=None, detail=None, 
                 duration=None, choice_share=None, row=None):
        if row:
            action_type = row['Result_type']
            detail = row['Result_detail']
            # TODO: default duration per result type
            duration = int(row['Result_duration']) if row['Result_duration'] else 0
            choice_share = int(row['Choice_share']) if row['Choice_share'] else 1
            
        all_actions.append(self)
        self.action_type = action_type
        self.state_name = state_name
        self.detail = detail
        if self.action_type == 'STATE_TRANSITION':
            self.detail = self.detail.upper()
        self.duration = duration
        self.choice_share = choice_share
        self.choice_total = 0
        self.next_action = None
        self.next_choice = None
        self.prev_action = prev_action
        self.prev_choice = prev_choice
        self.input_tuple = input_tuple
        
    def __str__(self):
        return '%s%s %s' % (self.action_type, ':' if self.detail else '',
                            str(self.detail))
        
class TextAction(GameAction):
    max_extra_details = 0
    pass

class GameState(object):
    next_id = 0
    def __init__(self, name):
        self.events = dict()
        self.name = name
        self.id = GameState.next_id
        GameState.next_id += 1
        
        all_states.append(self)
        state_name_ids[self.name] = self.id
        
    def __str__(self):
        return self.name
        
def read_state_data(statefile, allow_implicit):

    # First, a general validation pass with State definitions.
    # Then we do a final pass to add actions.
    
    # Lex/Syntax pass:
    with open(statefile) as csvfile:
        csvreader = csv.DictReader(csvfile)
        
        for required_heading in REQUIRED_HEADINGS:
            if required_heading not in csvreader.fieldnames:
                print("FATAL: %s:%d" % (statefile, 1))
                print(" Required heading '%s' not found." % required_heading)
                exit(1)

        result_detail_index = csvreader.fieldnames.index('Result_detail')
        for i in range(result_detail_index+1, len(csvreader.fieldnames)):
            if (csvreader.fieldnames[i]):
                print("FATAL: %s:%d" % (statefile, 1))
                print(" Expected only blank or no headings after Result_detail")
                exit(1)
        
        row_number = 0
        state_is_set = False
        
        for row in csvreader:
            row_number += 1
            if row['Input_type'] in IGNORE_INPUT_TYPES:
                continue # Skip blank and ignored (comment/action) lines
            if not state_is_set and row['Input_type'] != 'START_STATE':
                print("FATAL: %s:%d" % (statefile, row_number))
                print(','.join(row.values()))
                print("^~~~~~~ Input type not allowed without STATE_START first")
                exit(1)
            if row['Input_type'] == 'START_STATE':
                state_is_set = True
                # New state.
                if row['Input_detail'].upper() in state_name_ids:
                    print("FATAL: %s:%d" % (statefile, row_number))
                    print(','.join(row.values()))
                    print((" "*(len(row['Input_type'])+2)) + \
                          "^~~~~~~ Duplicate state definition")
                    exit(1)
                # TODO: Validate that other columns are empty.
                new_state = GameState(row['Input_detail'].upper())
                continue
                
            # TODO: Validate that the columns that should be numbers are 
            #       numbers.
                
            # If we're here, it's an action/event:
            if row['Input_type'] not in VALID_INPUT_TYPES:
                print("FATAL: %s:%d" % (statefile, row_number))
                print(','.join(row.values()))
                print("^~~~~~~ Unknown input type '%s'" % row['Input_type'])
                exit(1)
            if row['Result_type'] not in VALID_RESULT_TYPES:
                    print("FATAL: %s:%d" % (statefile, row_number))
                    print(','.join(row.values()))
                    print((" "*(len(row['Input_type'])+len(row['Input_detail'])+len(row['Choice_share'])+len(row['Result_duration'])+2)) + \
                          "^~~~~~~ Unknown result type '%s'" % str(row['Result_type']))
                    exit(1)
    
    # Now, all the explicit states have been loaded, so they all have IDs.
    # Time to process the results.
    
    with open(statefile) as csvfile:
        csvreader = csv.DictReader(csvfile)
        
        # We want to be able to accept multiple text options in a single row.
        #  So users are allowed to add as many extra columns as they want.
        #  Here, we are assigning them numbers, starting with 0.
        # First, determine where the Result_detail column is:
        result_detail_index = csvreader.fieldnames.index('Result_detail')
        # Earlier, we already validated that this is the last named column.
        #  Now, check whether there are additional unnamed columns. If so,
        #  count them.
        if len(csvreader.fieldnames) > result_detail_index+1:
            TextAction.max_extra_text_details = len(csvreader.fieldnames) - 1 - result_detail_index
            
        # Now, for every extra column, assign it a numeric key, starting with 0.
        #  This is nice because all the other keys are always strings, so this
        #  should not ever conflict with existing columns:
        for i in range(result_detail_index+1, len(csvreader.fieldnames)):
            csvreader.fieldnames[i] = i-result_detail_index-1 # 0-origined
        
        # Now let's get going.
        current_state = None
        
        for row in csvreader:
            row_number += 1
            if row['Input_type'] in IGNORE_INPUT_TYPES:
                continue # Skip blank and ignored (comment/action) lines
            if row['Input_type'] == 'START_STATE':
                # New state.
                current_state = all_states[state_name_ids[row['Input_detail'].upper()]]
                current_action = None
                continue
                    
            # If we're here, it means that the line is an action, not a state
            #  definition. We're ready to process the action definition.
            # There are a few possibilities:
            #  1. This could be a new event, meaning it is an Input tuple we
            #     have never seen before in the current state.
            #  2. This could be a new action choice for an existing event,
            #     meaning it's a repeat of a Input tuple that already exists
            #     in the current state.
            #  3. It's a continuation of an action sequence, meaning it is a
            #     CONTD Input_type.
            
            # We check for case 3 first.
            if row['Input_type'] == "CONTD":
                # This is a continuation of the current action sequence.
                # TODO: improve constructor:
                # TODO: determine whether it's text or not.
                # previous action is current_action, previous choice is None
                next_action = GameAction(current_action.input_tuple, 
                                         current_state.name, 
                                         current_action, None, row=row)
                current_action.next_action = next_action
                current_action = next_action
                continue
            
            # Now we know we're in case 1 or 2.            
            input_tuple = (row['Input_type'], row['Input_detail'])
            
            # If the input tuple already exists for this state, we know we're
            #  in case 2. If not, it's case 1.
            
                
            if input_tuple in current_state.events:
                # This is case 2. It's a new action choice for an existing
                # event.
                current_choice_share = 1
                if row['Choice_share']:
                    # If a choice share is provided, use it:
                    choice_share = int(row['Choice_share'])
                
                current_choice = current_state.events[input_tuple]
                while True:
                    current_choice.choice_total += current_choice_share
                    if current_choice.next_choice:
                        current_choice = current_choice.next_choice
                    else:
                        # current_choice.next_choice = None, so we are at
                        #  the choice - where we need to hook our new choice up.
                        break
                # Previous action is None, previous choice is current_choice.
                next_action = GameAction(input_tuple, current_state.name, 
                                         None, current_choice, row=row)
                next_action.choice_total = current_choice.choice_total
                current_choice.next_choice = next_action
            else:
                # No previous action, no previous choice:
                next_action = GameAction(input_tuple, current_state.name, 
                                         None, None, row=row)
                # This is case 1. We add to the state's events dictionary,
                #  where the input tuple is the key and the new state object
                #  is the value.
                current_state.events[input_tuple] = next_action
            current_action = next_action
            
        # TODO: Consider permitting implicit state definition again.
        
    # Now, build the state diagram.
    # Now we're going to build our pretty graph.
    state_graph = nx.MultiDiGraph()
    
    for state_name in all_states:
        state_graph.add_node(state_name)
    
    for action in all_actions:
        if action.action_type == 'STATE_TRANSITION':
            # We want to add an edge, but we want the label to be the action
            #  that starts the action sequence resulting in this state
            #  transition. So we'll follow the chain back to the initial
            #  action.
            label_action = action
            while label_action.prev_action:
                label_action = label_action.prev_action
                
            state_graph.add_edge(action.state_name, action.detail,
                                 label=str(action.input_tuple))
    
    return state_graph
