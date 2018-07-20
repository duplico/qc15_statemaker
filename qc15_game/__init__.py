REQUIRED_HEADINGS = ['Input_type', 'Input_detail', 'Choice_share', 
                     'Result_duration', 'Result_type', 'Result_detail']

IGNORE_STATES = ['EXAMPLE_NOTPARSED', 'SHEETNAMES']
VALID_INPUT_TYPES = ['ENTER', 'USER_IN', 'BUTTON', 'NET', 'TIMER', 'TIMER_R',
                     'CONTD', 'NOP']
IGNORE_INPUT_TYPES = ['', 'COMMENT', 'ACTIONS']
VALID_RESULT_TYPES = ['TEXT', 'SET_ANIM_TEMP', 'SET_ANIM_BG', 
                      'STATE_TRANSITION', 'OTHER', 'CLOSE', 'POP']
RESERVED_STATES = ['POP', 'POST']
SPECIAL_STATES = ['POP', 'GLOBAL']
