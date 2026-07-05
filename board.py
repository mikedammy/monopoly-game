from objects import (
    Property, Railroad, Utility,
    Go, Tax, FreeParking, GoToJail,
    CommunityChest, Chance, Jail
)

#------------------------------------------------------
# JAIL SINGLETON
# Created once here; GoToJail and state.py both reference it.
#------------------------------------------------------
jail = Jail()

#------------------------------------------------------
# ALL 40 SPACES IN ORDER (index = board position)
#------------------------------------------------------

# The Property class takes in the following arguments:
# colour, name, price, house_cost, mortgage_price, 
#redeem_price, rent_list


BOARD = [
    # 0
    Go(),

    # 1 - Brown
    Property('Brown', 'Mediterranean Avenue', 60, 50, 30, 33,
             [2, 10, 30, 90, 160, 250]),

    # 2
    CommunityChest(),

    # 3 - Brown
    Property('Brown', 'Baltic Avenue', 60, 50, 30, 33,
             [4, 20, 60, 180, 320, 450]),

    # 4
    Tax('Income Tax', 200),

    # 5
    Railroad('Reading Railroad'),

    # 6 - Light Blue
    Property('Light Blue', 'Oriental Avenue', 100, 50, 50, 55,
             [6, 30, 90, 270, 400, 550]),

    # 7
    Chance(),

    # 8 - Light Blue
    Property('Light Blue', 'Vermont Avenue', 100, 50, 50, 55,
             [6, 30, 90, 270, 400, 550]),

    # 9 - Light Blue
    Property('Light Blue', 'Connecticut Avenue', 120, 50, 60, 66,
             [8, 40, 100, 300, 450, 600]),

    # 10
    jail,   # "Just Visiting" when landed normally; Jail when sent here

    # 11 - Pink
    Property('Pink', 'St. Charles Place', 140, 100, 70, 77,
             [10, 50, 150, 450, 625, 750]),

    # 12
    Utility('Electric Company'),

    # 13 - Pink
    Property('Pink', 'States Avenue', 140, 100, 70, 77,
             [10, 50, 150, 450, 625, 750]),

    # 14 - Pink
    Property('Pink', 'Virginia Avenue', 160, 100, 80, 88,
             [12, 60, 180, 500, 700, 900]),

    # 15
    Railroad('Pennsylvania Railroad'),

    # 16 - Orange
    Property('Orange', 'St. James Place', 180, 100, 90, 99,
             [14, 70, 200, 550, 750, 950]),

    # 17
    CommunityChest(),

    # 18 - Orange
    Property('Orange', 'Tennessee Avenue', 180, 100, 90, 99,
             [14, 70, 200, 550, 750, 950]),

    # 19 - Orange
    Property('Orange', 'New York Avenue', 200, 100, 100, 110,
             [16, 80, 220, 600, 800, 1000]),

    # 20
    FreeParking(),

    # 21 - Red
    Property('Red', 'Kentucky Avenue', 220, 150, 110, 121,
             [18, 90, 250, 700, 875, 1050]),

    # 22
    Chance(),

    # 23 - Red
    Property('Red', 'Indiana Avenue', 220, 150, 110, 121,
             [18, 90, 250, 700, 875, 1050]),

    # 24 - Red
    Property('Red', 'Illinois Avenue', 240, 150, 120, 132,
             [20, 100, 300, 750, 925, 1100]),

    # 25
    Railroad('B&O Railroad'),

    # 26 - Yellow
    Property('Yellow', 'Atlantic Avenue', 260, 150, 130, 143,
             [22, 110, 330, 800, 975, 1150]),

    # 27 - Yellow
    Property('Yellow', 'Ventnor Avenue', 260, 150, 130, 143,
             [22, 110, 330, 800, 975, 1150]),

    # 28
    Utility('Water Works'),

    # 29 - Yellow
    Property('Yellow', 'Marvin Gardens', 280, 150, 140, 154,
             [24, 120, 360, 850, 1025, 1200]),

    # 30
    GoToJail(jail),

    # 31 - Green
    Property('Green', 'Pacific Avenue', 300, 200, 150, 165,
             [26, 130, 390, 900, 1100, 1275]),

    # 32 - Green
    Property('Green', 'North Carolina Avenue', 300, 200, 150, 165,
             [26, 130, 390, 900, 1100, 1275]),

    # 33
    CommunityChest(),

    # 34 - Green
    Property('Green', 'Pennsylvania Avenue', 320, 200, 160, 176,
             [28, 150, 450, 1000, 1200, 1400]),

    # 35
    Railroad('Short Line Railroad'),

    # 36
    Chance(),

    # 37 - Dark Blue
    Property('Dark Blue', 'Park Place', 350, 200, 175, 193,
             [35, 175, 500, 1100, 1300, 1500]),

    # 38
    Tax('Luxury Tax', 100),

    # 39 - Dark Blue
    Property('Dark Blue', 'Boardwalk', 400, 200, 200, 220,
             [50, 200, 600, 1400, 1700, 2000]),
]

#------------------------------------------------------
# COLOUR GROUPS
# Maps colour name -> list of Property objects in that group.
# Built automatically from BOARD so it never goes out of sync.
#------------------------------------------------------
COLOUR_GROUPS = {}
for space in BOARD:
    if isinstance(space, Property):
        COLOUR_GROUPS.setdefault(space.colour, []).append(space)

# Colours in board order (useful for display)
COLOUR_ORDER = [
    'Brown', 'Light Blue', 'Pink', 'Orange',
    'Red', 'Yellow', 'Green', 'Dark Blue'
]

#------------------------------------------------------
# HELPERS
#------------------------------------------------------

def get_space(position):
    """Return the space object at a board position (0-39)."""
    return BOARD[position % 40]


def get_colour_group(colour):
    """Return the list of Property objects for a colour group."""
    return COLOUR_GROUPS.get(colour, [])


def check_monopoly(colour, player_name):
    """Return True if player_name owns every property in the colour group."""
    group = get_colour_group(colour)
    if not group:
        return False
    return all(p.owner == player_name for p in group)


def get_railroad_count(player_name):
    """Return how many railroads a player owns."""
    return sum(1 for s in BOARD if isinstance(s, Railroad) and s.owner == player_name)


def get_utility_count(player_name):
    """Return how many utilities a player owns."""
    return sum(1 for s in BOARD if isinstance(s, Utility) and s.owner == player_name)


def nearest_railroad(position):
    """Return (space_object, board_index) of the nearest railroad ahead of position."""
    railroad_positions = [i for i, s in enumerate(BOARD) if isinstance(s, Railroad)]
    for rr_pos in railroad_positions:
        if rr_pos > position:
            return BOARD[rr_pos], rr_pos
    # Wrap around
    return BOARD[railroad_positions[0]], railroad_positions[0]


def nearest_utility(position):
    """Return (space_object, board_index) of the nearest utility ahead of position."""
    utility_positions = [i for i, s in enumerate(BOARD) if isinstance(s, Utility)]
    for u_pos in utility_positions:
        if u_pos > position:
            return BOARD[u_pos], u_pos
    return BOARD[utility_positions[0]], utility_positions[0]


def board_summary():
    """Print a readable overview of all 40 spaces."""
    for i, space in enumerate(BOARD):
        name = getattr(space, 'name', type(space).__name__)
        owner = getattr(space, 'owner', '-')
        print(f"[{i:02d}] {name:<30} owner: {owner}")
