from __future__ import print_function

import csv
import textwrap
import struct

import networkx as nx
from chardet.universaldetector import UniversalDetector

from qc15_game import *

all_actions = []
all_states = []
state_name_ids = dict()

row_number = 0
statefile = ''

all_text = []
next_text_id = 0

class GameTimer(object):
    def __init__(self, duration, recurring, result):
        self.duration = duration
        self.recurring = recurring
        self.result = result
        
    def pack(self):
        """
        typedef struct {
            /// The duration of this timer, in 1/32 of seconds.
            uint32_t duration;
            /// True if this timer should repeat.
            uint8_t recurring;
            uint16_t result_action_id;
        } game_timer_t;
        """
        pass


class GameInput(object):
    def __init__(self, text, result)
        if text no in all_text:
            all_text.append(text)
            next_text_id += 1
        self.result = result
        
class GameAction(object):
    max_extra_details = 0
    
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
        
        # If we're a member of a choice set, we need to link the existing 
        #  last element to ourself, and then we should increment every other 
        #  member's choice_total so they're all the same.
        if self.prev_choice:
            # Wire our previous choice up to us.
            self.prev_choice.next_choice = self
            # Now compute the choice total so far, also incrementing every
            #  previous choice's total by our choice share. (which will make
            #  them all equal, I hope I hope I hope)
            previous_choice = self.prev_choice
            while previous_choice:
                self.choice_total += previous_choice.choice_share
                previous_choice.choice_total += self.choice_share
                previous_choice = previous_choice.prev_choice
        
        # If we're in an action sequence, we need to tell the existing last
        #  element of that sequence that we come next.
        if self.prev_action:
            self.prev_action.next_action = self
        
        if self.action_type == 'STATE_TRANSITION':
            self.detail = self.detail.upper()
            if self.detail not in state_name_ids:
                # ERROR! Unless we're allowing implicit state declaration.
                if GameState.allow_implicit:
                    # Create a new game state for this transition.
                    new_state = GameState(self.detail)
                else:
                    # ERROR.                    
                    print("FATAL: %s:%d" % (statefile, row_number))
                    if row:
                        print(','.join(row.values()))
                        print(" "*(len(row['Input_type'])+len(row['Input_detail'])+len(row['Choice_share'])+len(row['Result_type']+len(row['Result_duration'])+6)) + "^")
                    print("Unknown state '%s'" % self.detail)
                    exit(1)
            self.detail = all_states[state_name_ids[self.detail]]
        
    def get_previous_action(self):
        if self.prev_action:
            return self.prev_action
        
        last_choice = self.prev_choice
        
        if not last_choice:
            # There are neither choices before us in the chain, nor an explicit
            #  previous action. That means that we are the first in the chain,
            #  so return None.
            return None
        
        # Find the first node in the choice set linked-list:
        while last_choice.prev_choice:
            last_choice = last_choice.prev_choice
        
        # Now last_choice holds the first node in the choice set. Return its
        #  previous action:
        return last_choice.prev_action
        
    @staticmethod
    def create_from_row(input_tuple, state, prev_action, prev_choice, row):
        # TODO: Consider permitting implicit state definition again.
        # TODO: Handle the integer versions
        if row['Result_type'] != 'TEXT':
            action =  GameAction(input_tuple, state.name, prev_action, 
                                 prev_choice, row=row)
            if input_tuple not in state.events:
                state.insert_event(input_tuple, action)
            return action
        # If we've gotten to this point, that means ... drumroll...
        # We're dealing with a TEXT row!
        
        duration = int(row['Result_duration']) if row['Result_duration'] else 0
        choice_share = int(row['Choice_share']) if row['Choice_share'] else 1
        
        # This means there's a couple of extra things we need to do.
        # We definitely need to generate the first action series. 
        first_action, last_action = GameAction.create_text_action_seq(
            input_tuple, 
            state.name, 
            prev_action, 
            prev_choice, 
            row['Result_detail'],
            duration,
            choice_share
        )
        
        # This gave us two actions, which may be the same as each other.        
        
        
        # See if this needs to be attached directly to an event:        
        if input_tuple not in state.events:
            # If so, we need to add the very first event in this chain.
            if input_tuple not in state.events:
                state.insert_event(input_tuple, first_action)
        
        if (0 not in row) or (not row[0]):
            # If this is the only column, we're done. Time to return
            #  last_action, which is what additional actions will need to
            #  link to.
            return last_action
        
        # If we're here it means that we have multiple text choices to deal
        #  with. We've saved the results of our first sequence creation call.
        #  Now we need to link some new choices to it.
        
        # We save first_action, because we need to link additional action
        #  choices to it. We save last_action, because this function needs to
        #  return the final action in an action sequence, so that the main
        #  generator function that called us can link additional actions to
        #  it, as needed.
        choices_generated = [(first_action, last_action)]
                
        for i in range(GameAction.max_extra_details):
            if not row[i]:
                break
            # i = index of previous choice in choices_generated
            # Each choice should link its first action to the previous choice
            f, l = GameAction.create_text_action_seq(
                input_tuple, 
                state.name, 
                None, # Previous action is reached through the choice set.
                choices_generated[i][0], # Wire the first actions together.
                row[i],
                duration,
                choice_share
            )
            choices_generated.append((f, l))
                
        # Since we're down here, it means we generated more than one choice.
        #  There's one final step to get everything working. We need to add a
        #  NOP action to aggregate all those choices back together to able
        #  single action sequence we can hand back off to the main
        #  generation function.
        
        # We leave the prev_action (which this will have as a stand-in) out of
        #  the constructor, because we don't want to trigger the automatic
        #  linking logic.
        nop_aggregator = GameAction(input_tuple, state.name, None, None,
                                    action_type='NOP', detail='', duration=0,
                                    choice_share=1)
        nop_aggregator.prev_action = choices_generated[0][1]
        
        # Wire up the next action for every one of our choices' last actions
        #  to the NOP aggregator. Then return it.
        for (first, last) in choices_generated:
            last.next_action = nop_aggregator
        
        return nop_aggregator
        
    @staticmethod
    def create_text_action_seq(input_tuple, state_name, prev_action,
                               prev_choice, detail, duration, choice_share):
        first_action = None
        prev_action = None
        text_frames = textwrap.wrap(detail, 24)
        if not text_frames:
            text_frames.append(' ')
        for frame in text_frames:
            action_type = 'TEXT'
            frame_text = frame
            
            # TODO: Validate the single variable constraint.
            
            if '$badgname' in frame:
                frame_text = frame.replace('$badgname', '%s', 1)
                action_type = 'TEXT_BADGEVAR'
            elif '$username' in frame:
                frame_text = frame.replace('$badgname', '%s', 1)
                action_type = 'TEXT_USERVAR'
            
            new_action = GameAction(input_tuple, state_name, prev_action,
                                    prev_choice, action_type=action_type,
                                    detail=frame_text, duration=duration,
                                    choice_share=choice_share)
            prev_action = new_action
            if not first_action:
                first_action = new_action
                prev_choice = None
        
        # Now, prev_action contains the last in the chain, and first_action
        #  contains the first. They may be the same.
        
        return (first_action, prev_action)
    
    def __str__(self):
        return '%s%s %s' % (self.action_type, ':' if self.detail else '',
                            str(self.detail))
        
    def __repr__(self):
        return self.__str__()
        
    def struct_text(self):
        ret = ""
        pass
        
class GameState(object):
    next_id = 0
    allow_implicit = False
    def __init__(self, name):
        self.events = dict()
        self.name = name
        self.id = GameState.next_id
        GameState.next_id += 1
        
        all_states.append(self)
        state_name_ids[self.name] = self.id
        
        self.entry_sequence_start = None
        self.timers = []
        self.inputs = []
    
    def insert_event(input_tuple, first_action):
        if input_tuple in self.events:
            print("FATAL: %s:%d" % (statefile, row_number))
            print("  Duplicate event insertion not allowed.")
            print("  This is likely a bug. Please alert George.")
            exit(1)
        self.events[input_tuple] = first_action
        # TODO: Process 
    
    def timers(self):
        timers = []
        recurring_timers = []
        for input_tuple, action in self.events.items():
            if input_tuple[0] == 'TIMER_R':
                recurring_timers.append((input_tuple, action))
            elif input_tuple[0] == 'TIMER':
                timers.append((input_tuple, action))
        
        # Now sort them. We need LONGEST FIRST within each list,
        #  then to append the lists, with non-recurring first.
        reverse_by_duration = lambda a: -int(a[0][1])
        timers.sort(key=reverse_by_duration)
        recurring_timers.sort(key=reverse_by_duration)
        
        return timers + recurring_timers
        
    def user_ins(self):
        return [(input_tuple, action) for (input_tuple, action) in self.events.items() if input_tuple[0] == 'USER_IN']
    
        # TODO: delete:
        # user_inputs = []
        
        # for input_tuple, action in self.events.items():
            # if input_tuple[0] == 'USER_IN':
                # user_inputs.append((input_tuple, action))
        
        # return user_inputs
        
    def entry_series(self):
        
        return self.events.get(('ENTER', ''), None)
        
    def __str__(self):
        return self.name
        
    def __repr__(self):
        return self.__str__()
        
    def struct_text(self):
        """
        typedef struct {
            // TODO: this id shouldn't be here.
            uint8_t id;
            uint16_t entry_series_id;
            uint8_t timer_series_len;
            game_timer_t timer_series[5];
            uint8_t input_series_len;
            game_user_in_t input_series[5];
        } game_state_t;
        """
        ret = ""
        pass
        
def read_states_and_validate(statefile):
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
        
        global row_number
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
            
            if row['Input_type'] == 'ENTER' and row['Input_detail']:
                print("FATAL: %s:%d" % (statefile, row_number))
                print(','.join(row.values()))
                print((" "*(len(row['Input_type'])+2)) + \
                      "^~~~~~~ Input_detail not allowed for ENTER input types")
                exit(1)
        
def read_actions(statefile_param):
    global statefile
    statefile = statefile_param
    
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
            GameAction.max_extra_details = len(csvreader.fieldnames) - 1 - result_detail_index
            
        # Now, for every extra column, assign it a numeric key, starting with 0.
        #  This is nice because all the other keys are always strings, so this
        #  should not ever conflict with existing columns:
        for i in range(result_detail_index+1, len(csvreader.fieldnames)):
            csvreader.fieldnames[i] = i-result_detail_index-1 # 0-origined
        
        # Now let's get going.
        current_state = None
        
        global row_number
        
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
                # previous action is current_action, previous choice is None
                next_action = GameAction.create_from_row(
                    current_action.input_tuple,
                    current_state,
                    current_action, None,
                    row
                )
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
                
                # Find the last action node in the choice set associated with
                #  the current input tuple.
                current_choice = current_state.events[input_tuple]
                while True:
                    if current_choice.next_choice:
                        current_choice = current_choice.next_choice
                    else:
                        # current_choice.next_choice = None, so we are at
                        #  the choice - where we need to hook our new choice up.
                        break
                # Previous action is None, previous choice is current_choice.
                next_action = GameAction.create_from_row(
                    input_tuple,
                    current_state,
                    None, current_choice,
                    row
                )
            else:
                # No previous action, no previous choice:
                next_action = GameAction.create_from_row(
                    input_tuple, 
                    current_state, 
                    None, None, 
                    row
                )
            current_action = next_action
        
def read_state_data(statefile, allow_implicit):

    GameState.allow_implicit = allow_implicit
    
    # First, a general validation pass with State definitions.
    # Then we do a final pass to add actions.
    
    # Lex/Syntax pass:
    read_states_and_validate(statefile)
    
    # Now, all the explicit states have been loaded, so they all have IDs.
    # Time to process the results.
    read_actions(statefile)
        
    # Now, build the state diagram.
    # Now we're going to build our pretty graph.
    state_graph = nx.MultiDiGraph()
    
    for state in all_states:
        state_graph.add_node(state.name)
        
    for action in all_actions:
        if action.action_type == 'STATE_TRANSITION':
            # We want to add an edge, but we want the label to be the action
            #  that starts the action sequence resulting in this state
            #  transition. So we'll follow the chain back to the initial
            #  action.
            label_action = action
            while label_action.get_previous_action():
                label_action = label_action.get_previous_action()
                
            state_graph.add_edge(action.state_name, action.detail,
                                 label=str(action.input_tuple))
    
    return state_graph
