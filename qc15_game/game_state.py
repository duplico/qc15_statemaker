from __future__ import print_function

import sys
import csv
import textwrap
import struct

import networkx as nx
from chardet.universaldetector import UniversalDetector

from qc15_game import *

all_actions = []
main_actions = []
aux_actions = []
all_states = []
main_text = [] # Lives in FRAM
aux_text = [] # Lives in flash

def text_addr(text):
    if text in main_text:
        return main_text.index(text)
    else:
        return len(main_text) + aux_text.index(text)

state_name_ids = dict()
closable_states = set()

max_inputs = 0
max_timers = 0
max_others = 0

all_other_input_descs = [
    'BADGESNEARBY0',
    'BADGESNEARBYSOME',
    'NAME_NOT_FOUND',
    'NAME_FOUND',
    'CONNECT_SUCCESS_NEW',
    'CONNECT_SUCCESS_OLD',
    'CONNECT_FAILURE'
]

all_other_output_descs = [
    'CUSTOMSTATEUSERNAME', # User name entry
    'NAMESEARCH',
    'SET_CONNECTABLE',
    'CONNECT',
    'STATUS_MENU',
]

all_animations = [
    'lightsSolidWhite', # TODO: Make these all caps, too.
    'lightsWhiteFader',
    'animSpinBlue',
    'whiteDiscovery',
    'animSolidBlue',
    'animSpinOrange',
    'animSolidGreen',
    'animSolidYellow',
    'animSpinGreen',
    'animSpinRed',
    'animSolidOrange',
    'animSolidRed',
    'animSpinWhite',
    'animSpinPink',
    'animFallBlue',
    'animFallYellow',
]

row_number = 0
row_lines = []
statefile = ''

class GameTimer(object):
    def __init__(self, duration, recurring, result):
        self.duration = duration
        self.recurring = recurring
        self.result = result
        
    def sort_key(self):
        # We want all one-time timers to go before recurring,
        #  and within those two we need them sorted by duration, longest first.
        # So, because a simple sort() is ascending, we want:
        #  high duration -> low sort_key
        key = -self.duration
        # And one-time -> low sort_key
        if not self.recurring:
            # Remember, key is negative.
            key = key * 1000000

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
        return struct.pack(
            '<LBxH',
            *self.as_int_sequence()
        )
            
    def as_int_sequence(self):
        return (
            int(self.duration * 32), # Convert from seconds to qc clock ticks
            self.recurring,
            self.result.id()
        )
            
    def as_struct_text(self):
        struct_text = "(game_timer_t){.duration=%d, .recurring=%d, " \
                      ".result_action_id=%d}" % self.as_int_sequence()
        return struct_text

    def __str__(self):
        return '%d %s' % (self.duration, 'R' if self.recurring else 'O')

    def __repr__(self):
        return str(self)

class GameInput(object):
    def __init__(self, text, result):
        if len(text) > 23:
            error(statefile, "Input text too long.", badtext=text)
        if text not in main_text:
            main_text.append(text)
            if text in aux_text:
                aux_text.remove(text)
        self.result = result
        self.text = text
    
    def pack(self):
        """
        typedef struct {
            uint16_t text_addr;
            uint16_t result_action_id;
        } game_user_in_t;
        """
        return struct.pack(
            '<HH',
            *self.as_int_sequence()
        )
            
    def as_int_sequence(self):
        return (
            text_addr(self.text),
            self.result.id()
        )
            
    def as_struct_text(self):
        struct_text = "(game_user_in_t){.text_addr=%d, .result_action_id=%d}" %\
            self.as_int_sequence()
        
        return struct_text
        
class GameOther(object):
    def __init__(self, desc, result):
        self.result = result
        self.desc = desc.upper()
        if self.desc in all_other_input_descs:
            self.id = all_other_input_descs.index(self.desc)
        else:
            self.id = len(all_other_input_descs)
            all_other_input_descs.append(self.desc)
    
    def pack(self):
        """
        typedef struct {
            uint16_t type_id;
            uint16_t result_action_id;
        } game_other_in_t;
        """
        return struct.pack(
            '<HH',
            *self.as_int_sequence()
        )
            
    def as_int_sequence(self):
        return (
            all_other_input_descs.index(self.desc),
            self.result.id()
        )
            
    def as_struct_text(self):
        struct_text = "(game_other_in_t){.type_id=%d, .result_action_id=%d}" %\
            self.as_int_sequence()
        
        return struct_text
        
class GameAction(object):
    max_extra_details = 0
    
    def __init__(self, input_tuple, state_name, prev_action, prev_choice,
                 action_type=None, detail=None, 
                 duration=0, choice_share=1, row=None, aux=False):
        if row:
            action_type = row['Result_type']
            detail = row['Result_detail']
            # TODO: default duration per result type
            duration = float(row['Result_duration']) if row['Result_duration'] else 0.0
            choice_share = int(row['Choice_share']) if row['Choice_share'] else 1
            
        all_actions.append(self)
        if (aux):
            aux_actions.append(self)
        else:
            main_actions.append(self)
        self.action_type = action_type
        self.state_name = state_name
        self.detail = detail
        self.duration = duration
        self.choice_share = choice_share
        self.choice_total = 0
        self.next_action = None
        self.next_choice = None
        self.prev_action = prev_action
        self.prev_choice = prev_choice
        self.input_tuple = input_tuple
            
        # Now, handle the specific disposition of our details based upon
        #  which action type we are:
        
        # If we're text, we need to load the text into the master text list:        
        if self.action_type.startswith("TEXT"):
            self.detail = self.detail.replace('`', '\x96')
            if aux and self.detail not in aux_text and self.detail not in main_text:
                    aux_text.append(self.detail)
            elif self.detail not in main_text:
                main_text.append(self.detail)
            
        if self.action_type == 'OTHER':
            self.detail = self.detail.upper().replace(' ', '_')
            self.detail = self.detail.replace('.', '')
            if self.detail not in all_other_output_descs:
                all_other_output_descs.append(self.detail)
            
        if self.action_type in ('PREVIOUS', 'PUSH', 'POP'):
            # Detail and duration are ignored.
            self.detail = ''
            self.duration = 0
            
        if self.action_type == 'CLOSE':
            # TODO
            pass
            
        if self.action_type.startswith("SET_ANIM"):
            global all_animations
            if self.detail == 'NONE':
                self.detail = None
            elif self.detail not in all_animations:
                all_animations.append(self.detail)
            
        if self.action_type == 'STATE_TRANSITION':
            self.detail = self.detail.upper()
            if self.detail not in state_name_ids:
                # ERROR! Unless we're allowing implicit state declaration.
                if GameState.allow_implicit:
                    # Create a new game state for this transition.
                    error(statefile, "Implicitly creating undefined state '%s'" % self.detail, badtext=self.detail, errtype='WARNING')
                    new_state = GameState(self.detail)
                    
                    # The state will display its name (truncated to 24 chars),
                    #  then return to the current state (the one that called it)
                    # TODO: use pop instead
                    
                    new_state_first_action = GameAction(
                        ('ENTER', ''),
                        self.detail[:24], 
                        None, 
                        None, 
                        action_type='TEXT', 
                        detail=self.detail[:24].upper(),
                        duration=5,
                    )
                    new_state.insert_event(('ENTER', ''), new_state_first_action)
                    GameAction(
                        ('ENTER', ''),
                        self.detail[:24], 
                        new_state_first_action, 
                        None, 
                        action_type='STATE_TRANSITION', 
                        detail=self.state_name,
                    )
                else:
                    # ERROR.                    
                    error(statefile, "Transition to undefined state '%s'" % self.detail, badtext=self.detail)
            self.detail = all_states[state_name_ids[self.detail]]
        
        # Finally, handle wiring up our linked-list structure:
        
        # If we're a member of a choice set, we need to link the existing 
        #  last element to ourself, and then we should increment every other 
        #  member's choice_total so they're all the same.
        self.choice_total = self.choice_share
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
            
    def id(self):
        return all_actions.index(self)
    
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
            assert last_choice.choice_total == last_choice.prev_choice.choice_total
            last_choice = last_choice.prev_choice
        
        # Now last_choice holds the first node in the choice set. Return its
        #  previous action:
        return last_choice.prev_action
        
    @staticmethod
    def create_from_row(input_tuple, state, prev_action, prev_choice, row):        
        if row['Result_type'] != 'TEXT':
            action =  GameAction(input_tuple, state.name, prev_action, 
                                 prev_choice, row=row)
            if input_tuple not in state.events:
                state.insert_event(input_tuple, action)
            return action
        # If we've gotten to this point, that means ... drumroll...
        # We're dealing with a TEXT row!
        
        duration = float(row['Result_duration']) if row['Result_duration'] else None
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
            choice_share,
            aux=False
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
                choice_share,
                aux=True
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
        # Link it to the LAST one, so that our assertion in the
        #  get_previous_action() method will detect malformed choice set
        #  choice totals.
        nop_aggregator.prev_action = choices_generated[-1][1]
        
        # Wire up the next action for every one of our choices' last actions
        #  to the NOP aggregator. Then return it.
        for (first, last) in choices_generated:
            last.next_action = nop_aggregator
        
        return nop_aggregator
        
    @staticmethod
    def create_text_action_seq(input_tuple, state_name, prev_action,
                               prev_choice, detail, duration, choice_share,
                               aux=False):
        first_action = None
        text_frames = textwrap.wrap(detail, 24)
        
        if not text_frames:
            text_frames.append(' ')

        if input_tuple[0] == 'TIMER_R' and len(text_frames) > 1:
            error(statefile, "Text wrap in recurring timer at marker, which causes unsatisfactory behavior.",
                  badtext=text_frames[1], errtype="WARNING")

        for frame in text_frames:
            action_type = 'TEXT'
            frame_text = frame
            
            if warn_on_wrap and len(text_frames) > 1 and frame_text.count(' ') == 0:
                error(statefile, "Detected single-word wrap. Consider revising.",
                      badtext=frame_text, errtype="WARNING")

            frame_dur = duration
            if frame_dur is None:
                frame_dur =  0.5 + 0.03125*len(frame_text)
            
            variable_count = sum(frame_text.count('$%s' % variable) for variable in ALLOWED_VARIABLES)
            if variable_count > 1:
                error(statefile, "Only one variable allowed in TEXT frame '%s'." % frame_text)
            
            for variable in ALLOWED_VARIABLES:
                fullvar = '$%s'%variable
                if fullvar in frame_text:
                    frame_text = frame_text.replace(fullvar, 
                                                    ALLOWED_VARIABLES[variable])
                    action_type = 'TEXT_%s' % variable.upper()
                    
            if '$' in frame and variable_count == 0:
                fakevar = frame.split('$')[1].split()[0].split(',')[0].strip()
                error(statefile, "Unrecognized variable '$%s', interpreting as literal." % fakevar,
                      badtext=fakevar, errtype="WARNING")
            
            new_action = GameAction(input_tuple, state_name, prev_action,
                                    prev_choice, action_type=action_type,
                                    detail=frame_text, duration=frame_dur,
                                    choice_share=choice_share, aux=aux)
                                    
            prev_action = new_action
            if not first_action:
                first_action = new_action
                prev_choice = None
        
        # Now, prev_action contains the last in the chain, and first_action
        #  contains the first. They may be the same.
        
        return (first_action, prev_action)
    
    def __str__(self):
        return '%d:%s%s %s (%d/32 sec) [%d/%d]' % (self.id(), self.action_type, ':' if self.detail else '',
                            str(self.detail), self.duration*32, self.choice_share,
                            self.choice_total)
        
    def __repr__(self):
        return self.__str__()
    
    def pack(self):
        """
        typedef struct {
            /// The action type ID.
            uint16_t type;
            /// Action detail number.
            /**
             ** In the event of an animation or change state, this is the ID of the
             ** target. In the event of text, this signifies the address of the pointer
             ** to the text in our text-storage system.
             */
            uint16_t detail;
            /// The duration of the action, which may or may not be valid for this type.
            uint16_t duration;
            /// The ID of the next action to fire after this one, or `ACTION_NONE`.
            uint16_t next_action_id;
            /// The ID of the next possible choice in this choice set, or `ACTION_NONE`.
            uint16_t next_choice_id;
            /// The share of the likelihood of this event firing.
            uint16_t choice_share;
            /// The total choice shares (denominator) of all choices in this choice set.
            uint16_t choice_total;
        } game_action_t;
        """
        return struct.pack(
            '<HHHHHHH',
            *self.as_int_sequence()
        )
    
    def detail_addr(self):
        if self.action_type.startswith('TEXT'):
            detail_addr = text_addr(self.detail)
        elif self.action_type.startswith('SET_ANIM'):
            detail_addr = all_animations.index(self.detail) if self.detail else NULL
        elif self.action_type == 'STATE_TRANSITION':
            detail_addr = all_states.index(self.detail)
        elif self.action_type == 'OTHER':
            detail_addr = all_other_output_descs.index(self.detail.upper())
        else:
            # TODO: OTHER TYPES
            # TODO: PUSH
            # TODO: CLOSE
            # TODO: POP
            detail_addr = 0
        return detail_addr
    
    def as_int_sequence(self):
        return (
            RESULT_TYPE_OUTPUT[self.action_type],
            self.detail_addr(),
            int(self.duration*32) if self.action_type.startswith('TEXT') else int(self.duration),
            self.next_action.id() if self.next_action else NULL,
            self.next_choice.id() if self.next_choice else NULL,
            self.choice_share,
            self.choice_total,
        )
    
    def as_struct_text(self):
        struct_text = "(game_action_t){%d, %d, %d, %d, %d, %d, %d}" % self.as_int_sequence()
        return struct_text
        
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
        self.other_ins = []
    
    def insert_event(self, input_tuple, first_action):
        if input_tuple in self.events:
            error(statefile, "Duplicate event insertion. This is likely a bug in this script. Alert george@queercon.org.",
                  badtext=input_tuple[1])
        self.events[input_tuple] = first_action
        if input_tuple[0] == 'ENTER':
            # This is the handle to our Enter event!
            self.entry_sequence_start = first_action
        
        if input_tuple[0] in ('TIMER', 'TIMER_R'):
            # This is a new timer event.
            # TODO: sort the timers.
            try:
                dur = int(input_tuple[1])
                if dur <=0:
                    raise "PROBLEM"
            except:
                error(statefile, "Could not convert '%s' to positive integer" % input_tuple[1],
                      row_number, badtext=input_tuple[1])
            
            self.timers.append(GameTimer(dur, input_tuple[0] == 'TIMER_R', 
                                         first_action))
            self.timers.sort(key=GameTimer.sort_key) # Always in order.
            
        if input_tuple[0] == 'USER_IN':
            self.inputs.append(GameInput(input_tuple[1], first_action))
            
        if input_tuple[0] == 'NET':
            self.other_ins.append(GameOther(input_tuple[1], first_action))
        
    def __str__(self):
        return '%d %s' % (self.id, self.name)
        
    def __repr__(self):
        return self.__str__()
        
    def pack(self):
        """
        typedef struct {
            uint16_t entry_series_id;
            uint8_t timer_series_len;
            uint8_t input_series_len;
            uint8_t other_series_len;

            game_timer_t timer_series[X];
            game_user_in_t input_series[X];
            game_other_in_t other_series[X];
        } game_state_t;
        """
        bytes = ''
        bytes += struct.pack('<HBBBx', *self.as_int_sequence())

        for timer in self.timers:
            bytes += timer.pack()
        # TODO: This is a dumb way to multiply:
        for i in range(max_timers - len(self.timers)):
            bytes += '\x00'*8

        for input in self.inputs:
            bytes += input.pack()
        for i in range(max_inputs - len(self.inputs)):
            bytes += '\x00'*4
        
        for other in self.other_ins:
            bytes += other.pack()
        for i in range(max_others - len(self.other_ins)):
            bytes += '\x00'*4

        return bytes

            
    def as_int_sequence(self):
        return (
            self.entry_sequence_start.id() if self.entry_sequence_start else 0xFFFF,
            len(self.timers),
            len(self.inputs),
            len(self.other_ins)
        )
            
    def as_struct_text(self):
        struct_text = "(game_state_t){.entry_series_id=%d, .timer_series_len=%d, .input_series_len=%d, .other_series_len=%d, " % self.as_int_sequence()
        struct_text += ".timer_series=%s, .input_series=%s, .other_series=%s}" %\
            (
                '{%s}' % (','.join(map(GameTimer.as_struct_text, self.timers)),),
                '{%s}' % (','.join(map(GameInput.as_struct_text, self.inputs)),),
                '{%s}' % (','.join(map(GameOther.as_struct_text, self.other_ins)),),
            )
        
        return struct_text
        
def error(statefile, message, row=None, col=None, badtext='', errtype='FATAL'):
    if row is None:
        row = row_number
    if col is None and badtext != '' and row:
        col = row_lines[row].upper().find(badtext.upper())
    print("%s: %s:%d:" % (errtype, statefile, row), file=sys.stderr)
    if row:
        print(row_lines[row], file=sys.stderr)
        if col is not None:
            pad = ' ' * col
            print(pad + '^')
    print('   ' + message, file=sys.stderr)
    print()
    if errtype != 'WARNING':
        exit(1)
        
def read_states_and_validate(statefile):
    with open(statefile) as csvfile:
        global row_number
        global row_lines
        row_number = 1
        state_is_set = False
    
        csvreader = csv.DictReader(csvfile)
        
        for required_heading in REQUIRED_HEADINGS:
            if required_heading not in csvreader.fieldnames:
                error(statefile, 
                      "Required heading '%s' not found." % required_heading)

        result_detail_index = csvreader.fieldnames.index('Result_detail')
        for i in range(result_detail_index+1, len(csvreader.fieldnames)):
            if (csvreader.fieldnames[i]):
                error(statefile, "Expected only blank or no headings after Result_detail", 
                      row=row_number, badtext=csvreader.fieldnames[i])
        
        no_contd_allowed = 1
        for row in csvreader:
            row_number += 1
            if row['Input_type'] == '':
                for field in csvreader.fieldnames:
                    if row[field]:
                        error(statefile, "Blank input type, but line has more contents.",
                              badtext=row[field], errtype="WARNING")
            if row['Input_type'] in IGNORE_INPUT_TYPES:
                continue # Skip blank and ignored (comment/action) lines
            if not state_is_set and row['Input_type'] != 'START_STATE':
                error(statefile, "Input type '%s' not allowed before START_STATE" % row['Input_type'], 
                      badtext=row['Input_type'])
            if row['Input_type'] == 'START_STATE':
                state_is_set = True
                # New state.
                if row['Input_detail'].upper() in state_name_ids:
                    error(statefile, "Duplicate state definition '%s'" % row['Input_detail'],
                          badtext=row['Input_detail'])
                # TODO: Validate that other columns are empty.
                GameState(row['Input_detail'].upper())
                continue
                
            # TODO: Validate that the columns that should be numbers are 
            #       numbers.
                
            # If we're here, it's an action/event:
            if row['Input_type'] not in VALID_INPUT_TYPES:
                error(statefile, "Unknown input type '%s'" % row['Input_type'],
                          badtext=row['Input_type'])
            
            if row['Result_type'] not in VALID_RESULT_TYPES:
                error(statefile, "Unknown result type '%s'" % row['Result_type'],
                          badtext=row['Result_type'])
            
            if no_contd_allowed and row['Input_type'] == 'CONTD':
                error(statefile, "CONTD not allowed after state transitions.")
                          
            if row['Result_type'] == 'STATE_TRANSITION':
                no_contd_allowed = 1
            else:
                no_contd_allowed = 0
                
            
            if row['Result_type'] not in VALID_RESULT_TYPES:
                error(statefile, "Unknown result type '%s'" % row['Result_type'],
                          badtext=row['Result_type'])
            
            if row['Input_type'] == 'ENTER' and row['Input_detail']:
                error(statefile, "Input_detail not allowed for ENTER input types",
                      badtext=row['Input_detail'])
            
            # TODO: Enforce STATE TRANSITION must be last in an action sequence.
            
        
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
        global row_lines
        row_number = 1
    
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
        
def pack_text(text):
    assert len(text)<25 # Need at least one null term
    return text + '\x00'*(25-len(text))

def pack_structs():
    packed_text = ''
    for s in main_text:
        packed_text += pack_text(s)
    for s in aux_text:
        packed_text += pack_text(s)
    
    packed_actions = ''
    for a in all_actions:
        packed_actions += a.pack()

    packed_states = ''
    for s in all_states:
        packed_states += s.pack()
    
    return dict(text=packed_text, actions=packed_actions, states=packed_states)


def display_data_str(outfile=sys.stdout):
    print("#define ALL_ACTIONS_LEN %d" % len(all_actions), file=outfile)
    print("#define ALL_TEXT_LEN %d" % len(main_text), file=outfile)
    print("#define all_states_len %d" % len(all_states), file=outfile)

    print("#define MAX_TIMERS %d" % max_timers, file=outfile)
    print("#define MAX_INPUTS %d" % max_inputs, file=outfile)
    print("#define MAX_OTHERS %d" % max_others, file=outfile)

    # TODO:
    print("#define GAME_ANIMS_LEN %d" % len(all_animations), file=outfile)
    print("", file=outfile)
    print("// %s" % ", ".join(all_animations), file=outfile)
    
    # print("uint8_t main_text[][25] = {%s};" % ','.join(map(lambda a: '"%s"' % a.replace('"', '\\"').strip(), main_text)), file=outfile)
    # print("", file=outfile)
    
    # print("uint8_t aux_text[][25] = {%s};" % ','.join(map(lambda a: '"%s"' % a.replace('"', '\\"').strip(), aux_text)), file=outfile)
    # print("", file=outfile)

    # main_actions_structs = map(GameAction.as_struct_text, main_actions)
    # print("game_action_t main_actions[] = {%s};" % ', '.join(main_actions_structs), file=outfile)
    # print("", file=outfile)

    # aux_actions_structs = map(GameAction.as_struct_text, aux_actions)
    # print("game_action_t aux_actions[] = {%s};" % ', '.join(aux_actions_structs), file=outfile)
    # print("", file=outfile)
    
    # all_states_structs = map(GameState.as_struct_text, all_states)
    # print("game_state_t all_states[] = {%s};" % ', '.join(all_states_structs), file=outfile)
    # print("", file=outfile)
    
    i=0
    for other_type in all_other_input_descs:
        print("#define SPECIAL_%s %d" % (other_type, i), file=outfile)
        i += 1
        
    for state in all_states:
        print("#define STATE_ID_%s %d" % (state.name.replace(' ', '_'), state.id), file=outfile)

    i=0
    for other_type in all_other_output_descs:
        print("#define OTHER_ACTION_%s %d" % (other_type, i), file=outfile)
        i += 1
        
    print("#define CLOSABLE_STATES %d" % len(closable_states), file=outfile)
    
def read_state_data(statefile, allow_implicit, do_cull_nops):
    GameState.allow_implicit = allow_implicit
    
    # We do an initial pass to load the contents of the text into a buffer.
    global row_lines
    row_lines = [line.strip() for line in open(statefile)]
    row_lines = [''] + row_lines
    # Then a general validation pass with State definitions.
    # Then we do a final pass to add actions.
    
    # Lex/Syntax pass:
    read_states_and_validate(statefile)
    
    # Now, all the explicit states have been loaded, so they all have IDs.
    # Time to process the results.
    try:
        read_actions(statefile)
    except Exception as e:
        error(statefile, "PYTHON ERROR: %s" % e.message)
        
    # Get rid of any no-ops that we can delete.
    if do_cull_nops:
        cull_nops()
        
    # Now, build the state diagram.
    # Now we're going to build our pretty graph.
    state_graph = nx.MultiDiGraph()
    
    global max_inputs, max_others, max_timers

    for state in all_states:
        state_graph.add_node(state)
        if len(state.inputs) > max_inputs:
            max_inputs = len(state.inputs)
        if len(state.timers) > max_timers:
            max_timers = len(state.timers)
        if len(state.other_ins) > max_others:
            max_others = len(state.other_ins)
        
    for action in all_actions:
        if action.action_type == 'STATE_TRANSITION':
            state_graph.add_edge(all_states[state_name_ids[action.state_name]], 
                                 action.detail, label=str(action.input_tuple))
        

    for action in all_actions:
        if action.action_type == 'PREVIOUS':
            node = all_states[state_name_ids[action.state_name]]
            for predecessor in state_graph.predecessors(node):
                state_graph.add_edge(
                    node, predecessor, label=str(action.input_tuple)+' PREVIOUS'
                )

    undirected = state_graph.to_undirected()
    if not nx.is_connected(undirected):
        error(statefile, "Detected that the state graph may not be connected!",
              row=0, col=0, errtype="WARNING")

    
    for action in all_actions:
        if action.action_type == 'CLOSE':
            closable_states.add(action.state_name)

    for state in all_states:
        bad_problem = True
        for successor in state_graph.successors(state):
            if successor not in closable_states:
                bad_problem = False
                break
        if bad_problem:
            error(statefile, "All successor states of %s are closable!" % state.name, 
                  row=0, col=0, errtype="WARNING")

    return state_graph

def cull_nops():
    # Everything about action IDs are auto-computing.
    
    nops_to_delete = set()
    
    for before_nop in all_actions:
        # This doesn't cover all POSSIBLE cases, but it does cover all
        #  ALLOWED cases: (except that NOPs at the start of an action sequence
        #  are not deleted. btw, those are the only ones that could be in a 
        #  choice set.
        if before_nop.next_action and before_nop.next_action.action_type == 'NOP':
            nop = before_nop.next_action
            after_nop = nop.next_action
            if after_nop:
                after_nop.prev_action = before_nop
            before_nop.next_action = after_nop
            nops_to_delete.add(nop)
    
    for action in nops_to_delete:
        all_actions.remove(action)
        if action in main_actions:
            main_actions.remove(action)
        else:
            aux_actions.remove(action)
            
def escape_action(action):
    return str(action).replace(':', ' ').replace('\\', '/').replace('\x96', '`')

def get_action_graph():
    action_graph = nx.MultiDiGraph()
    # for action in all_actions:
        # action_graph.add_node(str(action))
        
    for state in all_states:
        if state.id == 0:
            action_graph.add_node(str(state).replace(':', ' '), shape='star')
        else:
            action_graph.add_node(str(state).replace(':', ' '), shape='box')
        for input_tuple in state.events:
            if not state.events[input_tuple]:
                continue
            action_graph.add_edge(
                str(state).replace(':', ' '),
                str(state.events[input_tuple]).replace(':', ' ').replace('\x96', '`'),
                label=str(input_tuple)
            )

    for action in all_actions:
        if action.next_action:
            action_graph.add_edge(escape_action(action), escape_action(action.next_action),
                                  label="next")
        if action.next_choice:
            action_graph.add_edge(escape_action(action), escape_action(action.next_choice),
                                  label="alt")
        if action.action_type == 'STATE_TRANSITION':
            action_graph.add_edge(
                escape_action(action),
                str(action.detail).replace(':', ' ')
            )
    
    # TODO: Add PREVIOUS lines!

    undirected = action_graph.to_undirected()
    if not nx.is_connected(undirected):
        error(statefile, "Detected that the action graph may not be connected!",
              row=0, col=0, errtype="WARNING")

    return action_graph

    