Introduction
============

The Queercon 15 on-badge game is implemented with a specialized kind of state
machine. The specification for the game is read from a spreadsheet, which is
loaded as a comma-separated value (CSV) file, by a tool called Statemaker.

Statemaker has the following features:

Validation
    Read in a CSV file and perform sanity-checking validation to make sure the 
    result is a working game.
              
State diagram generation
    Produce a GraphViz .dot file in order to visualize the game's state machine.
                
Intermediate code generation 
    Generate code readable by the on-badge interpreter, in Intel Hex format.
                
The Specification Language
==========================

Overview
--------

First, a few basic concepts. A *state* describes our current position in the
game. The player is always in exactly one state. While in a state, there are
several ways that something could happen. Either the badge generates an event,
for example with a timer or by receiving a message over the radio; or the user
generates one, for example by selecting an option on the screen using their
buttons.

The first row of the spreadsheet MUST include the following fields: 
``Input_type``, ``Input_detail``, ``Choice_share``, ``Result_type``, and 
``Result_detail``. It MAY include empty columns, and those columns MAY be in
any order, except that of the named columns ``Result_detail`` MUST be the last
header. Additional columns are interpreted only for ``TEXT`` ``Result_type``.


Events
------

An *event* is the basic input to the state machine on the badge. Specifically,
events are what cause any kind of action to happen. These are things like
radio activity, timers, state entry, and user activity. An event is uniquely
described by two characteristics: the ``Input_type`` and the ``Input_detail``.
The pair of those two fields is called an *Input tuple*.

The following events are supported:

``ENTER``
    A state is entered. ``Input_detail`` is ignored.
    
``USER_IN``
    The user selects an option on their menu on the bottom screen on the badge.
    ``Input_detail`` specifies the text of that option.
    
``TIMER``
    A one-time timer. ``Input_detail`` is the length, in seconds, between the
    completion of the state's ``ENTER`` action series, and the generation of the
    timer event.
    
``TIMER_R``
    A recurring timer. ``Input_detail`` is the length, in seconds, of the timer.
    That is, a recurring timer will fire every ``Input_detail`` seconds. Note 
    that ambiguity is resolved in decreasing order of specificity. That is, if a
    one-time timer and a recurring timer both have the option of firing at the
    same time, the one-time timer will fire an event, and the recurring timer
    will skip its iteration. Similarly, if there are multiple recurring timers
    and more than one might be able to fire on one timestep, ties are resolved
    in favor of the longer duration timer.
    
``NET``
    A network event - something has happened over the radio. These are all
    custom-coded, so ``Input_detail`` should be a brief, descriptive identifier
    used consistently throughout the state specification. For example,
    ``NewBadgeDownloadedMyCode`` might refer to an event where a badge who has
    never connected to our badge before has initiated a connection; or
    ``MoreThanTenBadgesNearby`` might refer to a situation where the number of
    badges nearby has increased above 10.
    
Special Input_types
~~~~~~~~~~~~~~~~~~~

The following special input types are also supported:

``CONTD``
    Continues the above action sequence. See Action Sequences, below.
    
``ACTIONS``, ``COMMENT``, or blank
    The entire row is ignored by Statemaker.
    
``START_STATE``
    Begins the specification of a new state. The state's name is indicated by
    ``Input_detail``.
    
Actions
-------

*Actions* are the outcomes of events. These are how the game interacts with the
player and moves through the state machine. Each action corresponds to a single
task that the badge might do: for example, setting an animation, printing text,
or changing the state. An individual action is fully described by an *action 
tuple*, which is made up of the ``Action_type``, the ``Action_detail``, and the
``Action_duration``.

The following actions are supported:

``TEXT``
    Displays a text message on the upper screen of the badge in a typewriter
    effect. The contents of ``Action_detail`` specify the text. If the text is
    too long for the screen, then Statemaker will automatically break it up
    into multiple actions and chain them together. As a special case, multiple
    text options may be placed on the same row, in immediately subsequent
    columns to ``Action_detail``, and these will be interpreted as alternative
    text options and selected from randomly when the action is invoked.
    ``Action_duration`` is the number of seconds for the text to remain
    stationary on the screen before the next action may fire.
    
``SET_ANIM_BG``
    Sets a new background animation for the ring LEDs. The ``Result_detail``
    contains the name of the animation to select. Consistently use a short,
    descriptive name, such as ``Rainbow`` or ``AllWhite``. This animation will
    repeat until a new background animation is set. ``Action_duration`` is 
    ignored.
    
``SET_ANIM_TEMP``
    Invokes a temporary background animation for the ring LEDs. The 
    ``Result_detail`` field contains the name of the animation to select.
    Consistently use a short, descriptive name, such as ``Rainbow`` or 
    ``AllWhite``. This action type shares the same pool of animations as 
    ``SET_ANIM_BG``. ``Result_duration`` is the number of loops to repeat the 
    animation. The next action in the sequence fires immediately.

``CLOSE``
    Permanently CLOSES the current state, making it never again reachable. Any
    event that could result in this state being reached will not fire, and
    and user input option that would result in this state being reached will
    not be presented to the user. ``Result_detail`` is ignored, and 
    ``Result_duration`` is ignored.

``STATE_TRANSITION``
    Changes states to the state named in ``Result_detail``. ``Result_duration`` 
    is ignored.
    
``PUSH``
    Saves the current state to a special storage location. USE OF THIS FEATURE 
    IS DISCOURAGED. ``Result_detail`` is ignored. ``Result_duration`` is 
    ignored. 
    
``POP``
    Loads the state most recently saved by a ``PUSH`` action, and performs a
    state transition to that state. USE OF THIS FEATURE IS DISCOURAGED.
    ``Result_detail`` is ignored. ``Result_duration`` is ignored.
    
``PREVIOUS``
    Loads the state that we most recently left to reach the current state, and
    performs a state transition to it. ``Result_detail`` is ignored. 
    ``Result_duration`` is ignored.
    
Combining Actions
-----------------

Actions may be combined in two main ways: the first is in *action sequences*, 
in which a series of actions are fired, one after the other, as the result of a
single event. The second is in *choice sets*, allowing the badge to randomly 
decide which of a set of action sequences will be chosen to execute as the
result of an event.

There is also a third special ``TEXT``-only action combination type, which only
applies to ``TEXT`` actions, allowing (1) a long TEXT action to be split
automatically into an action sequence, and (2) alternative TEXT choices to be
placed in an arbitrary number of columns immediately following 
``Result_detail``.

Implementation details
~~~~~~~~~~~~~~~~~~~~~~

Choice sets and action sequences are implemented using a sort of modified 
two-dimensional linked list structure. Horizontally, each action is a node in
a "choice set" linked list, and vertically each action is a node in an "action
sequence" linked list.

Under the hood, each action has two pointers to other actions: ``next_action`` 
and ``next_choice`` (either of which may take the null-interpreted value of 
``ACTION_NONE``). When the badge completes its current action, it examines 
the current action's ``next_action`` field. If that field is ``ACTION_NONE``, 
then the current action sequence is concluded. If that field is a pointer to 
another action, then that action is loaded and becomes the *first candidate 
action*.

Once the first candidate action is loaded, its ``next_choice`` field is 
examined. If ``next_choice`` is ``ACTION_NONE``, then it represents a simple 
action, and it is executed with no further analysis. If ``next_choice`` is 
instead a pointer to another action, then the badge evaluates the entire set of
actions on the horizontal ("choice set") linked list originated by that action.
Based on those actions' choice shares, and a pseudorandom number generated by 
the badge, one of those actions is selected as the next one to execute.

Action Sequences
~~~~~~~~~~~~~~~~

An *action sequence* is defined as a series of actions that are executed in 
order, as the result of an event. Excluding TEXT expansions, action sequences
are created using the special ``Input_type`` of ``CONTD``. A ``CONTD`` input 
type signals to Statemaker that the results specified in its row should be 
attached to the above action as its "next" action.

Choice Sets
~~~~~~~~~~~

A choice set allows a single event to randomly select between multiple action
sequences to execute. When a state definition in the spreadsheet contains more
than one copy of the same unique input tuple (that is, an ``Input_type``,
``Input_detail`` pair), then statemaker interprets that as to create a choice 
set. A choice set has the special characteristic of a ``Choice_share``, which 
defaults to 1 if not specified. Within a given choice set, every action 
sequence's choice share is summed, and the likelihood of an action sequence in 
a choice set being executed upon the invocation of its event is equal to the 
action sequence's choice share, divided by the total of every choice share of 
every action sequence in the choice set.

For example, if an event (``Input_type``, ``Input_detail``) of (TIMER, 20) 
appears three times in a state, like so::

    Input_type, Input_detail, Choice_share, Result_type, Result_detail
    TIMER, 20,  , TEXT, 12.5% chance
    TIMER, 20, 2, TEXT, 25% chance
    TIMER, 20, 5, TEXT, 62.5% chance
    
Then, for the event ``(TIMER, 20)``, a choice set will be generated, containing
three different action sequences (each of which is 1 action long). The first
entry has a blank choice share, which defaults to 1. Therefore, the sum of
the choice shares for the choice set is 8, so each action sequence's odds of
being executed upon the timer firing is its choice share (1, 2, or 5) divided
by 8.

TEXT Expansion
~~~~~~~~~~~~~~

As introduced above, ``TEXT`` actions have a special set of combination types.
The first is long text automatic sequence generation. The second is alternative
automatic choice set generation.

In a text action type, the ``Action_detail`` contains the actual text that the
badge will display. Because the badge's screens only have 24 characters, and
arbitrary length characters are accepted in the spreadsheet, statemaker will
automatically break longer text display actions into a series of text actions,
as if a series of ``CONTD`` input types had been applied to break the text up.

Automatic TEXT action sequences MAY have an alternative display behavior, such
as a shorter pause, or different typing behavior, depending on the
implementation details.

Additionally, to provide more variety for text responses, a TEXT action may
have more than one possible string to display. Alternate text for a TEXT action
is provided in the columns immediately to the right of the ``Result_detail``
column (which, as noted above, must be the rightmost named column).

When statemaker encounters alternate text details in a text action, it
(1) applies its automated text splitting capability to create a set of action
sequences out of the alternate text options, and then (2) aggregates those
sequences into a special kind of choice set, with evenly weighted choice shares,
so that one of the options - regardless of its length - will be chosen when
that text action is reached.