import random

#------------------------------------------------------
# MY MONOPOLY GAME
#------------------------------------------------------

STARTING_CASH = 1500
MAX_HOTELS = 12  # per official rules

#------------------------------------------------------
# BOARD CLASSES
#------------------------------------------------------

class Bank:
    n_banks = 0
    MAX_HOUSES = 32
    MAX_HOTELS = 12
    CURRENT_HOUSES = 0
    CURRENT_HOTELS = 0

    def __init__(self):
        if Bank.n_banks >= 1:
            raise ValueError("One bank already exists and there can only be one bank.")
        Bank.n_banks += 1

    @classmethod
    def can_build_house(cls):
        return cls.CURRENT_HOUSES < cls.MAX_HOUSES

    @classmethod
    def can_build_hotel(cls):
        return cls.CURRENT_HOTELS < cls.MAX_HOTELS

    @classmethod
    def build_house(cls):
        cls.CURRENT_HOUSES += 1

    @classmethod
    def build_hotel(cls):
        cls.CURRENT_HOTELS += 1
        cls.CURRENT_HOUSES -= 4

    @classmethod
    def sell_house(cls):
        if cls.CURRENT_HOUSES > 0:
            cls.CURRENT_HOUSES -= 1

    @classmethod
    def sell_hotel(cls):
        if cls.CURRENT_HOTELS > 0:
            cls.CURRENT_HOTELS -= 1
        cls.CURRENT_HOUSES += 4

    @classmethod
    def reset(cls):
        cls.CURRENT_HOUSES = 0
        cls.CURRENT_HOTELS = 0


class Property:

    no_of_props = 0

    def __init__(
        self, colour, name, price,
        house_cost, mortgage_price, redeem_price,
        rent_list
    ):
        self.name = name
        self.colour = colour
        self.price = price
        self.house_cost = house_cost
        self.mortgage_price = mortgage_price
        self.redeem_price = redeem_price
        self.rent_list = rent_list  # [base, 1h, 2h, 3h, 4h, hotel]

        self.__rent = self.rent_list[0]
        self.__n_houses = 0
        self.__hotel = False
        self.__owner = 'Bank'
        self.__is_mortgaged = False
        self.__is_monopolised = False
        self.__logs = []

        Property.no_of_props += 1

    @property
    def logs(self):
        return self.__logs

    @property
    def rent(self):
        return self.__rent

    @property
    def n_houses(self):
        # Returns int: 0-4 for houses, 5 for hotel
        return 5 if self.__hotel else self.__n_houses

    @property
    def n_houses_str(self):
        # Human-readable house/hotel label
        return 'Hotel' if self.__hotel else f'{self.__n_houses} houses'

    @property
    def has_hotel(self):
        return self.__hotel

    @property
    def owner(self):
        return self.__owner

    @owner.setter
    def owner(self, player):
        self.__logs.append(f"Player {player.name} buys {self.name} from {self.__owner}")
        self.__owner = player.name

    @property
    def is_mortgaged(self):
        return self.__is_mortgaged

    @is_mortgaged.setter
    def is_mortgaged(self, state):
        if state not in [True, False]:
            raise ValueError("Invalid state option!")
        message = f"{self.__owner} {'mortgaged' if state else 'redeemed'} {self.name} for {self.mortgage_price if state else self.redeem_price}"
        self.__logs.append(message)
        self.__is_mortgaged = state

    @property
    def is_monopolised(self):
        return self.__is_monopolised

    @is_monopolised.setter
    def is_monopolised(self, state):
        if state not in [True, False]:
            raise ValueError('Invalid state')

        # Only adjust base rent (index 0); houses/hotel rent stays fixed
        if state and not self.__is_monopolised:
            if not self.__hotel and self.__n_houses == 0:
                self.__rent = self.rent_list[0] * 2
        elif not state and self.__is_monopolised:
            if not self.__hotel and self.__n_houses == 0:
                self.__rent = self.rent_list[0]

        self.__is_monopolised = state

    def build_house(self, group):
        if self.__is_mortgaged:
            return False, "Cannot build on a mortgaged property."
        if not self.__is_monopolised:
            return False, "You haven't monopolised this colour group yet."
        if self.__hotel:
            return False, "Property is already at maximum improvement (Hotel)."
            
        # The Even-Building Check
        if any(p.n_houses < self.n_houses for p in group):
            return False, "You must build evenly across the colour group."
            
        if not Bank.can_build_house():
            return False, "Bank has no houses left."

        next_houses = self.__n_houses + 1

        if next_houses == 5:
            if not Bank.can_build_hotel():
                return False, "Bank has no hotels left"
            Bank.build_hotel()
            self.__hotel = True
            self.__n_houses = 0
            self.__rent = self.rent_list[5]
            t_me = 'a Hotel'
        else:
            Bank.build_house()
            self.__n_houses = next_houses
            self.__rent = self.rent_list[self.__n_houses]
            t_me = f'{self.__n_houses} house(s)'

        message = f"Player {self.__owner} spent ${self.house_cost} to upgrade {self.name} to {t_me}"
        self.__logs.append(message)
        return True, message

    def sell_house(self, group):
        if not self.__hotel and self.__n_houses == 0:
            return False, 0, "No houses to sell."
            
        # The Even-Selling Check
        if any(p.n_houses > self.n_houses for p in group):
            return False, 0, "You must sell evenly across the colour group."

        sell_value = self.house_cost // 2

        if self.__hotel:
            self.__hotel = False
            self.__n_houses = 4
            self.__rent = self.rent_list[4]
            Bank.sell_hotel()
            desc = 'Hotel downgraded to 4 houses'
        else:
            self.__n_houses -= 1
            self.__rent = self.rent_list[self.__n_houses] if self.__n_houses > 0 else (
                self.rent_list[0] * 2 if self.__is_monopolised else self.rent_list[0]
            )
            Bank.sell_house()
            desc = f'Sold 1 house, now {self.__n_houses} house(s)'

        message = f"Player {self.__owner}: {desc}. Received ${sell_value}."
        self.__logs.append(message)
        return True, sell_value, message

    def reset(self):
        # Bypass the even-sell rule for hard resets by returning inventory directly
        if self.__hotel:
            Bank.sell_hotel()
        for _ in range(self.__n_houses):
            Bank.sell_house()

        self.__hotel = False
        self.__n_houses = 0
        self.__owner = 'Bank'
        self.__is_mortgaged = False
        self.__is_monopolised = False
        self.__rent = self.rent_list[0]
        self.__logs.append(f"Successfully reset {self.name}")
        return 1

    
    
    def reset(self):
        # Sell down all improvements first
        if self.__hotel:
            for _ in range(5):
                self.sell_house()
        elif self.__n_houses >= 1:
            for _ in range(self.__n_houses):
                self.sell_house()

        self.__owner = 'Bank'
        self.__is_mortgaged = False
        self.__is_monopolised = False
        self.__rent = self.rent_list[0]
        self.__logs.append(f"Successfully reset {self.name}")
        return 1


class Railroad:

    no_railroads = 0
    RENT_TABLE = {1: 25, 2: 50, 3: 100, 4: 200}

    def __init__(self, name):
        if Railroad.no_railroads >= 4:
            raise ValueError("Max number of railroads (4) already instantiated.")

        self.__name = name
        self.__cost = 200
        self.price = self.__cost
        self.mortgage_price = 100
        self.redeem_price = 110
        self.__rent = 25
        self.__owner = 'Bank'
        self.__is_mortgaged = False
        self.__logs = []

        Railroad.no_railroads += 1

    @property
    def name(self):
        return self.__name

    @property
    def cost(self):
        return self.__cost

    @property
    def owner(self):
        return self.__owner

    @owner.setter
    def owner(self, player):
        self.__logs.append(f"{player.name} purchases {self.__name} from {self.__owner}")
        self.__owner = player.name

    @property
    def rent(self):
        return self.__rent

    @rent.setter
    def rent(self, multiple):
        if multiple not in self.RENT_TABLE:
            raise ValueError("Multiple must be 1–4.")
        self.__rent = self.RENT_TABLE[multiple]

    @property
    def is_mortgaged(self):
        return self.__is_mortgaged

    @is_mortgaged.setter
    def is_mortgaged(self, state):
        if state not in [True, False]:
            raise ValueError("Invalid state option!")
        message = f"{self.__owner} {'mortgaged' if state else 'redeemed'} {self.__name} for {self.mortgage_price if state else self.redeem_price}"
        self.__logs.append(message)
        self.__is_mortgaged = state

    def reset(self):
        self.__owner = 'Bank'
        self.__is_mortgaged = False
        self.__rent = 25
        self.__logs.append(f"Successfully reset {self.__name}")
        return 1


class Utility:

    n_utilities = 0

    def __init__(self, name):
        if Utility.n_utilities >= 2:
            raise ValueError("Two utilities already exist.")

        self.__name = name
        self.__cost = 150
        self.price = self.__cost
        self.mortgage_price = 75
        self.redeem_price = 82.5
        self.__is_mortgaged = False
        self.__rent_mult = 4
        self.__owner = 'Bank'
        self.__logs = []

        Utility.n_utilities += 1

    @property
    def name(self):
        return self.__name

    @property
    def cost(self):
        return self.__cost

    @property
    def owner(self):
        return self.__owner

    @owner.setter
    def owner(self, player):
        self.__logs.append(f"{player.name} purchases {self.__name} from {self.__owner}")
        self.__owner = player.name

    @property
    def is_mortgaged(self):
        return self.__is_mortgaged

    @is_mortgaged.setter
    def is_mortgaged(self, state):
        if state not in [True, False]:
            raise ValueError("Invalid state option!")
        message = f"{self.__owner} {'mortgaged' if state else 'redeemed'} {self.__name} for {self.mortgage_price if state else self.redeem_price}"
        self.__logs.append(message)
        self.__is_mortgaged = state

    @property
    def rent_mult(self):
        return self.__rent_mult

    @rent_mult.setter
    def rent_mult(self, mult):
        if mult not in [4, 10]:
            raise ValueError("Multiplier must be 4 (1 utility) or 10 (both utilities).")
        self.__rent_mult = mult

    def rent_due(self, dice_roll):
        if dice_roll < 2 or dice_roll > 12:
            raise ValueError("Invalid dice roll (must be 2–12).")
        return self.__rent_mult * dice_roll

    def reset(self):
        self.__owner = 'Bank'
        self.__is_mortgaged = False
        self.__rent_mult = 4
        self.__logs.append(f"Successfully reset {self.__name}")
        return 1


#------------------------------------------------------
# SPECIAL BOARD SPACES
#------------------------------------------------------

class Go:
    SALARY = 200
    name = 'Go'

    @staticmethod
    def pay_salary(player):
        player.cash += Go.SALARY
        player.logs = f"Collected $200 salary from Go."


class Tax:
    """Income Tax (Space 4) and Luxury Tax (Space 38)."""

    def __init__(self, name, amount):
        self.name = name
        self.amount = amount

    def collect(self, player):
        player.cash -= self.amount
        player.logs = f"Paid {self.name}: ${self.amount}"


class FreeParking:
    name = 'Free Parking'

    def land(self, player):
        player.logs = "Landed on Free Parking. Nothing happens."


class GoToJail:
    name = 'Go To Jail'

    def __init__(self, jail):
        self.jail = jail

    def send(self, player):
        player.position = 10  # jump directly, no salary
        self.jail.add_prisoner(player)


class Jail:
    name = 'Jail / Just Visiting'
    FINE = 50

    def __init__(self):
        self.__prisoners = {}  # {name: turns_in_jail}

    @property
    def prisoners(self):
        return list(self.__prisoners.keys())

    def add_prisoner(self, player):
        if player.name in self.__prisoners:
            print(f"{player.name} is already in jail.")
            return
        self.__prisoners[player.name] = 0
        player.jailed = True

    def release(self, player):
        if player.name not in self.__prisoners:
            print(f"{player.name} is not in jail.")
            return
        del self.__prisoners[player.name]
        player.jailed = False

    def increment_turn(self, player):
        """Call each turn a jailed player fails to escape. Returns turns served."""
        if player.name in self.__prisoners:
            self.__prisoners[player.name] += 1
            return self.__prisoners[player.name]
        return 0


#------------------------------------------------------
# CARD CLASSES
#------------------------------------------------------

class CommunityChest:
    name = 'Community Chest'

    _CARD_EFFECTS = {
        'advance to go':      {'type': 'move', 'dest': 0, 'collect_go': True},
        'bank error':         {'type': 'cash', 'amount': 200},
        'doctor fees':        {'type': 'cash', 'amount': -50},
        'stock sale':         {'type': 'cash', 'amount': 50},
        'jail free':          {'type': 'jail_free'},
        'go to jail':         {'type': 'go_to_jail'},
        'holiday fund':       {'type': 'cash', 'amount': 100},
        'tax refund':         {'type': 'cash', 'amount': 20},
        'birthday':           {'type': 'collect_all', 'amount': 10},
        'life insurance':     {'type': 'cash', 'amount': 100},
        'hospital fees':      {'type': 'cash', 'amount': -100},
        'school fees':        {'type': 'cash', 'amount': -50},
        'consultancy fee':    {'type': 'cash', 'amount': 25},
        'beauty contest':     {'type': 'cash', 'amount': 10},
        'inheritance':        {'type': 'cash', 'amount': 100},
        'street repairs':     {'type': 'street_repairs', 'house_cost': 40, 'hotel_cost': 115},
    }

    _DETAILS = {
        'advance to go':   'Advance to GO: Move token to Space 0. Collect $200.',
        'bank error':      'Bank error in your favour: Collect $200.',
        'doctor fees':     "Doctor's fees: Pay $50.",
        'stock sale':      'From sale of stock: Collect $50.',
        'jail free':       'Get Out of Jail Free: Keep this card until needed.',
        'go to jail':      'Go to Jail! Do not pass Go, do not collect $200.',
        'holiday fund':    'Holiday Fund matures: Collect $100.',
        'tax refund':      'Income tax refund: Collect $20.',
        'birthday':        'It is your birthday: Collect $10 from every other player.',
        'life insurance':  'Life insurance matures: Collect $100.',
        'hospital fees':   'Pay hospital fees of $100.',
        'school fees':     'Pay school fees of $50.',
        'consultancy fee': 'Receive $25 consultancy fee.',
        'beauty contest':  'Second prize in a beauty contest: Collect $10.',
        'inheritance':     'You inherit $100.',
        'street repairs':  'Street repairs: Pay $40/house and $115/hotel you own.',
    }

    _deck = list(_CARD_EFFECTS.keys())
    random.shuffle(_deck)

    @classmethod
    def draw(cls, player, all_players=None, board=None, jail=None):
        card = cls._deck[0]
        cls._deck.append(cls._deck.pop(0))  # rotate to bottom

        detail = cls._DETAILS[card]
        effect = cls._CARD_EFFECTS[card]
        print(f"[Community Chest] {detail}")
        player.logs = f"Drew Community Chest: {detail}"

        etype = effect['type']

        if etype == 'cash':
            amount = effect['amount']
            player.cash += amount
            if amount > 0:
                print(f"  >> {player.name} received ${amount} from the Bank.")
            else:
                print(f"  >> {player.name} paid ${abs(amount)} to the Bank.")

        elif etype == 'move':
            player.position = effect['dest']
            if effect.get('collect_go'):
                Go.pay_salary(player)
            print(f"  >> {player.name} advances to Go and collects $200.")

        elif etype == 'jail_free':
            player.comm_cards = card
            print(f"  >> {player.name} keeps the Get Out of Jail Free card.")

        elif etype == 'go_to_jail':
            if jail:
                jail.add_prisoner(player)
            print(f"  >> {player.name} is sent to Jail.")

        elif etype == 'collect_all' and all_players:
            collected = 0
            for other in all_players:
                if other.name != player.name and other.cash >= effect['amount']:
                    other.cash -= effect['amount']
                    player.cash += effect['amount']
                    collected += effect['amount']
            print(f"  >> {player.name} collected ${collected} in birthday money.")

        elif etype == 'street_repairs' and board:
            houses = sum(
                b._Property__n_houses for b in board
                if isinstance(b, Property) and b.owner == player.name
            )
            hotels = sum(
                1 for b in board
                if isinstance(b, Property) and b.owner == player.name and b._Property__hotel
            )
            total = houses * effect['house_cost'] + hotels * effect['hotel_cost']
            player.cash -= total
            player.logs = f"Street repairs cost: ${total} ({houses} houses, {hotels} hotels)"
            print(f"  >> {player.name} paid ${total} for street repairs ({houses} houses, {hotels} hotels).")

        return card


class Chance:
    name = 'Chance'

    _CARDS = [
        'advance to go',
        'advance to illinois',
        'advance to st charles',
        'advance to nearest utility',
        'advance to nearest railroad',
        'bank dividend',
        'jail free',
        'go back three',
        'go to jail',
        'general repairs',
        'speeding fine',
        'advance to boardwalk',
        'elected chairman',
        'building loan',
        'reading railroad',
    ]

    _DETAILS = {
        'advance to go':              'Advance to GO. Collect $200.',
        'advance to illinois':        'Advance to Illinois Avenue. If you pass Go collect $200.',
        'advance to st charles':      'Advance to St. Charles Place. If you pass Go collect $200.',
        'advance to nearest utility': 'Advance to nearest Utility. Pay 10× dice roll if owned.',
        'advance to nearest railroad':'Advance to nearest Railroad. Pay 2× rent if owned.',
        'bank dividend':              'Bank pays dividend of $50.',
        'jail free':                  'Get Out of Jail Free card. Keep until used.',
        'go back three':              'Go back 3 spaces.',
        'go to jail':                 'Go to Jail. Do not pass Go, do not collect $200.',
        'general repairs':            'General repairs: Pay $25/house and $100/hotel.',
        'speeding fine':              'Speeding fine: Pay $15.',
        'advance to boardwalk':       'Advance to Boardwalk.',
        'elected chairman':           'Elected Chairman: Pay each player $50.',
        'building loan':              'Building loan matures: Collect $150.',
        'reading railroad':           'Take a trip to Reading Railroad. If you pass Go collect $200.',
    }

    # Board positions for named destinations
    _DESTINATIONS = {
        'advance to go':          0,
        'advance to illinois':    24,
        'advance to st charles':  11,
        'advance to boardwalk':   39,
        'reading railroad':       5,
    }

    _deck = list(_CARDS)
    random.shuffle(_deck)

    @classmethod
    def draw(cls, player, all_players=None, board=None, jail=None):
        card = cls._deck[0]
        cls._deck.append(cls._deck.pop(0))

        detail = cls._DETAILS[card]
        print(f"[Chance] {detail}")
        player.logs = f"Drew Chance: {detail}"

        if card in cls._DESTINATIONS:
            dest = cls._DESTINATIONS[card]
            old_pos = player.position
            player.position = dest
            if dest < old_pos:
                Go.pay_salary(player)
                print(f"  >> {player.name} advances to space {dest} and collects $200 passing Go.")
            else:
                print(f"  >> {player.name} advances to space {dest}.")

        elif card == 'advance to nearest utility':
            pass  # Game engine resolves nearest utility and prints result

        elif card == 'advance to nearest railroad':
            pass  # Game engine resolves nearest railroad and prints result

        elif card == 'bank dividend':
            player.cash += 50
            print(f"  >> {player.name} received $50 bank dividend.")

        elif card == 'jail free':
            player.comm_cards = card
            print(f"  >> {player.name} keeps the Get Out of Jail Free card.")

        elif card == 'go back three':
            player.position = player.position - 3
            print(f"  >> {player.name} moves back 3 spaces to space {player.position}.")

        elif card == 'go to jail':
            if jail:
                jail.add_prisoner(player)
            print(f"  >> {player.name} is sent to Jail.")

        elif card == 'general repairs' and board:
            houses = sum(
                b._Property__n_houses for b in board
                if isinstance(b, Property) and b.owner == player.name
            )
            hotels = sum(
                1 for b in board
                if isinstance(b, Property) and b.owner == player.name and b._Property__hotel
            )
            total = houses * 25 + hotels * 100
            player.cash -= total
            print(f"  >> {player.name} paid ${total} for general repairs ({houses} houses, {hotels} hotels).")

        elif card == 'speeding fine':
            player.cash -= 15
            print(f"  >> {player.name} paid $15 speeding fine.")

        elif card == 'elected chairman' and all_players:
            total_paid = 0
            for other in all_players:
                if other.name != player.name:
                    player.cash -= 50
                    other.cash += 50
                    total_paid += 50
            print(f"  >> {player.name} paid ${total_paid} total as elected chairman ($50 to each player).")

        elif card == 'building loan':
            player.cash += 150
            print(f"  >> {player.name} received $150 from building loan.")

        return card


#------------------------------------------------------
# PLAYER CLASS
#------------------------------------------------------

class Player:

    n_players = 0

    def __init__(self, name):
        self.name = name

        self.__properties = []
        self.__cash = STARTING_CASH
        self.__position = 0   # Space 0 = Go
        self.__in_jail = False
        self.__jail_turns = 0
        self.__comm_cards = []
        self.__logs = [
            f'Starting cash: ${self.__cash}',
            f'Starting position: {self.__position} (Go)'
        ]

        Player.n_players += 1

    @property
    def cash(self):
        return self.__cash

    @cash.setter
    def cash(self, amount):
        self.__cash = amount

    @property
    def logs(self):
        return self.__logs

    @logs.setter
    def logs(self, log):
        self.__logs.append(log)

    @property
    def position(self):
        return self.__position

    @position.setter
    def position(self, new_pos):
        """Accepts an absolute board position (0–39)."""
        self.__position = new_pos % 40
        self.__logs.append(f"Moved to space {self.__position}")

    def move(self, steps):
        """Move forward by dice roll, wrapping around the board."""
        old_pos = self.__position
        new_pos = (old_pos + steps) % 40
        self.__position = new_pos
        passed_go = new_pos < old_pos or steps >= 40
        self.__logs.append(f"Rolled {steps}, moved from {old_pos} to {new_pos}")
        return passed_go

    @property
    def properties(self):
        return self.__properties

    @properties.setter
    def properties(self, prop_name):
        self.__logs.append(f"Purchased {prop_name}")
        self.__properties.append(prop_name)

    @property
    def comm_cards(self):
        return self.__comm_cards

    @comm_cards.setter
    def comm_cards(self, card):
        self.__comm_cards.append(card)

    @property
    def jail_turns(self):
        return self.__jail_turns

    @jail_turns.setter
    def jail_turns(self, val):
        self.__jail_turns = val

    @property
    def jailed(self):
        return self.__in_jail

    @jailed.setter
    def jailed(self, state):
        if state not in [True, False]:
            raise ValueError("Invalid state for jail.")
        if self.__in_jail == state:
            msg = f'{self.name} is already in jail' if self.__in_jail else f'{self.name} is not in jail'
            raise ValueError(msg)
        self.__logs.append("You went to jail." if state else "You left jail.")
        self.__in_jail = state
        if state:
            self.__jail_turns = 0
        else:
            self.__jail_turns = 0

    def use_jail_card(self):
        if 'jail free' not in self.__comm_cards:
            return False
        self.__comm_cards.remove('jail free')
        self.__logs.append("Used Get Out of Jail Free card.")
        return True

    def pay_rent(self, other, amount):
        if amount < 0:
            raise ValueError("Amount must be non-negative.")
        if self.__cash < amount:
            raise ValueError(f"{self.name} cannot afford rent of ${amount}.")
        self.__logs.append(f"Paid rent of ${amount} to {other.name}.")
        other.logs = f"Collected rent of ${amount} from {self.name}."
        self.__cash -= amount
        other.cash += amount

    def net_worth(self, board):
        """Cash + half mortgage value of all owned properties."""
        total = self.__cash
        for space in board:
            if isinstance(space, (Property, Railroad, Utility)) and space.owner == self.name:
                total += space.mortgage_price
        return total

    def is_bankrupt(self, amount_owed, board):
        return self.net_worth(board) < amount_owed

    def __repr__(self):
        return f"Player('{self.name}', cash=${self.__cash}, pos={self.__position})"


#------------------------------------------------------
# DICE
#------------------------------------------------------

class Dice:

    @staticmethod
    def roll():
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        return d1, d2, d1 + d2, d1 == d2  # die1, die2, total, is_double
