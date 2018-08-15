__author__ = "George Louthan @duplico"
__copyright__ = "(c) 2018, George Louthan"
__license__ = "MIT"
__email__ = "duplico@dupli.co"

REQUIRED_HEADINGS = ['Input_type', 'Input_detail', 'Choice_share', 
                     'Result_duration', 'Result_type', 'Result_detail']

IGNORE_STATES = ['EXAMPLE_NOTPARSED', 'SHEETNAMES']
VALID_INPUT_TYPES = ['ENTER', 'USER_IN', 'NET', 'TIMER', 'TIMER_R',
                     'CONTD']
IGNORE_INPUT_TYPES = ['', 'COMMENT', 'ACTIONS']
VALID_RESULT_TYPES = ['TEXT', 'SET_ANIM_TEMP', 'SET_ANIM_BG', 
                      'STATE_TRANSITION', 'OTHER', 'CLOSE', 'POP', 'PUSH',
                      'PREVIOUS', 'NOP']

RESULT_TYPE_OUTPUT = {
    'SET_ANIM_TEMP' : 0,
    'SET_ANIM_BG' : 1,
    'STATE_TRANSITION' : 2,
    'PUSH' : 3,
    'POP' : 4,
    'PREVIOUS' : 5,
    'CLOSE' : 6,
    'NOP' : 7,
    'TEXT' : 16,
    'TEXT_BADGENAME' : 17,
    'TEXT_USER_NAME' : 18,
    'TEXT_CNT' : 19,
    'TEXT_CNCTDNAME' : 20,
    'OTHER' : 100
}
                      
ALLOWED_VARIABLES = {
    'badgename' : '%s',
    'user_name' : '%s',
    'cnt' : '%d',
    'cnctdname' : '%s',
}

NULL = 0xFFFF

warn_on_wrap = True
