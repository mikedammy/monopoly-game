#cat > /mnt/user-data/outputs/bots.py << 'ENDOFFILE'
"""
bots.py — Rule-based bot players: Easy, Medium, Hard.

Each bot exposes one public method:
    take_bot_turn(game, result) -> None

game.py calls this instead of prompting a human when the current player is a bot.
"""

import time
import random
from objects import Property, Railroad, Utility
from board import BOARD, get_colour_group, check_monopoly, get_railroad_count

SLEEP = 0.6


def _sleep():
    time.sleep(SLEEP)


def _announce(player, msg):
    print(f"  [BOT/{player.name}] {msg}")
    _sleep()


# ─────────────────────────────────────────────────────────────────────────────
# BOARD QUERY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _owned(player, types=(Property, Railroad, Utility)):
    return [s for s in BOARD if isinstance(s, types) and s.owner == player.name]


def _unimproved_owned(player):
    return [
        s for s in _owned(player)
        if not isinstance(s, Property) or s.n_houses == 0
    ]


def _colour_owned_count(player, colour):
    return sum(1 for s in get_colour_group(colour) if s.owner == player.name)


def _colour_size(colour):
    return len(get_colour_group(colour))


def _get_space(name):
    return next((s for s in BOARD if getattr(s, 'name', None) == name), None)


def _properties_unowned_in_colour(colour):
    return [s for s in get_colour_group(colour) if s.owner == 'Bank']


def _opponent_owns_colour_count(player, colour, game):
    return sum(
        1 for s in get_colour_group(colour)
        if s.owner != 'Bank' and s.owner != player.name
    )


def evaluate_board_risk(bot_player, game):
    """
    Returns the highest single rent value among all spaces owned by opponents.
    Used as a dynamic cash buffer baseline by Medium and Hard bots.
    """
    max_rent = 0
    for space in BOARD:
        if not isinstance(space, (Property, Railroad, Utility)):
            continue
        if space.owner == 'Bank' or space.owner == bot_player.name:
            continue
        if space.is_mortgaged:
            continue
        if isinstance(space, Property):
            rent = space.rent
        elif isinstance(space, Railroad):
            rent = space.rent
        else:
            rent = space.rent_mult * 7
        if rent > max_rent:
            max_rent = rent
    return max_rent


def _bank_houses_available():
    from objects import Bank
    return Bank.MAX_HOUSES - Bank.CURRENT_HOUSES


# ─────────────────────────────────────────────────────────────────────────────
# BASE CLASS
# ─────────────────────────────────────────────────────────────────────────────

class BaseBot:
    tier = 'base'

    def __init__(self, player):
        self.player = player

    def jail_decision(self, game):
        raise NotImplementedError

    def _handle_jail(self, game):
        decision = self.jail_decision(game)
        if decision == 'card' and self.player.comm_cards:
            _announce(self.player, "Uses Get Out of Jail Free card.")
            game.use_jail_card(self.player)
        elif decision == 'pay':
            if self.player.cash >= game.JAIL_FINE:
                _announce(self.player, f"Pays ${game.JAIL_FINE} jail fine to get out.")
                game.pay_jail_fine(self.player)
            else:
                _announce(self.player, "Can't afford fine — rolls for doubles.")
        else:
            _announce(self.player, "Stays in jail and rolls for doubles.")

    def should_buy(self, space, game):
        raise NotImplementedError

    def handle_purchase(self, space, game):
        if self.should_buy(space, game):
            success = game.confirm_purchase(self.player, space)
            if success:
                _announce(self.player, f"Buys {space.name} for ${space.price}. Cash: ${self.player.cash}")
                return True
            else:
                _announce(self.player, f"Can't afford {space.name} — goes to auction.")
                return False
        else:
            _announce(self.player, f"Passes on {space.name} — goes to auction.")
            return False

    def auction_max_bid(self, space, current_high, game):
        return 0

    def evaluate_incoming_trade(self, offer_side, ask_side, initiator, game):
        raise NotImplementedError

    def receive_trade_offer(self, offer_side, ask_side, initiator, game):
        # Entry point for trade routing
        accepted = self.evaluate_incoming_trade(offer_side, ask_side, initiator, game)
        if accepted:
            _announce(self.player, f"Accepts trade offer from {initiator.name}.")
            return 'accept'
        else:
            _announce(self.player, f"Rejects trade offer from {initiator.name}.")
            return 'reject'

    # In bots.py inside the BaseBot class
    def generate_counter_offer(self, human_offer, human_ask, human_player, game):
        """Default base method: Bots do not counter by default."""
        return None
    
    def post_roll_actions(self, game):
        pass

    def take_bot_turn(self, game, result):
        if self.player.jailed:
            self._handle_jail(game)
            if self.player.jailed:  # Still in jail after decision — end turn
                self.post_roll_actions(game)
                _announce(self.player, "Ends turn.")
                game.next_turn()
                return

        # Resolve purchase on current space
        if result.get('action') == 'purchase_decision':
            space = _get_space(result['space'])
            bought = self.handle_purchase(space, game)
            if not bought:
                from game import run_english_auction
                run_english_auction(game, space)

        # If doubles were rolled and player isn't jailed, take bonus roll(s)
        while result.get('extra_roll') and not self.player.jailed and game.active:
            _announce(self.player, "Rolled doubles — taking bonus roll.")
            result = game.take_turn()
            if result.get('action') == 'purchase_decision':
                space = _get_space(result['space'])
                bought = self.handle_purchase(space, game)
                if not bought:
                    from game import run_english_auction
                    run_english_auction(game, space)

        self.post_roll_actions(game)
        _announce(self.player, "Ends turn.")
        game.next_turn()



# ─────────────────────────────────────────────────────────────────────────────
# EASY BOT  — "The Impulse Buyer"
# ─────────────────────────────────────────────────────────────────────────────

class EasyBot(BaseBot):
    tier = 'easy'

    def jail_decision(self, game):
        return 'roll'

    def should_buy(self, space, game):
        return self.player.cash >= space.price

    def auction_max_bid(self, space, current_high, game):
        return min(space.price, self.player.cash)

    def post_roll_actions(self, game):
        if self.player.cash <= 200:
            self._maybe_trade(game)
            return
        buildable = [
            s for s in BOARD
            if isinstance(s, Property)
            and s.owner == self.player.name
            and s.is_monopolised
            and not s.is_mortgaged
            and not s.has_hotel
        ]
        if buildable:
            space = random.choice(buildable)
            if self.player.cash - space.house_cost > 200:
                group = get_colour_group(space.colour)
                success, msg = space.build_house(group)

                if success:
                    self.player.cash -= space.house_cost
                    _announce(self.player, f"Randomly builds house on {space.name}.")
                # (Optional) You can add an else clause to handle/log the failure if needed
                # but for an EasyBot, skipping is perfectly fine.


        if self.player.cash <= 0:
            candidates = _unimproved_owned(self.player)
            if candidates:
                space = random.choice(candidates)
                if not space.is_mortgaged:
                    space.is_mortgaged = True
                    self.player.cash += space.mortgage_price
                    _announce(self.player, f"Randomly mortgages {space.name} to clear debt.")

    def _face_value(self, side):
        """Simple face-value calculation used by EasyBot (no strategic multipliers)."""
        return side['cash'] + sum(
            (_get_space(p).price if _get_space(p) else 0) for p in side['properties']
        )

    def _completes_monopoly(self, properties, player):
        for p_name in properties:
            space = _get_space(p_name)
            if isinstance(space, Property):
                if _colour_owned_count(player, space.colour) == _colour_size(space.colour) - 1:
                    return True
        return False

    def evaluate_incoming_trade(self, offer_side, ask_side, initiator, game):
        # Rule: Will not trade down its last property overall
        owned_props = [s for s in BOARD if getattr(s, 'owner', '') == self.player.name and isinstance(s, Property)]
        if len(owned_props) == 1 and ask_side['properties']:
            if owned_props[0].name in ask_side['properties']:
                return False

        incoming_val = self._face_value(offer_side)
        outgoing_val = self._face_value(ask_side)

        if outgoing_val == 0:
            return incoming_val > 0

        # Monopoly-completing trades get a discount on the threshold
        if self._completes_monopoly(offer_side['properties'], self.player):
            return incoming_val >= 0.8 * outgoing_val

        return incoming_val >= 1.5 * outgoing_val

    def evaluate_counter_offer(self, offer_side, ask_side, initiator, game):
        """
        Lenient evaluation for counters received in response to EasyBot's own proposals.
        EasyBot accepts a counter if what it gives out is at most 2× what it gets back.
        """
        incoming_val = self._face_value(offer_side)
        outgoing_val = self._face_value(ask_side)
        if outgoing_val == 0:
            return incoming_val > 0
        return outgoing_val <= 2.0 * incoming_val

    def generate_counter_offer(self, human_offer, human_ask, human_player, game):
        """EasyBot does not generate strategic counters — it either accepts or walks away."""
        return None

    def _maybe_trade(self, game):
        """
        EasyBot scans for any monopoly it is one property away from and offers
        ANY unimproved property it owns in exchange. No colour-tier restriction.
        """
        from trades import bot_propose_trade
        ALL_COLOURS = ['Brown', 'Light Blue', 'Pink', 'Orange', 'Red', 'Yellow', 'Green', 'Dark Blue']

        for colour in ALL_COLOURS:
            group = get_colour_group(colour)
            owned = _colour_owned_count(self.player, colour)
            size  = _colour_size(colour)
            if owned != size - 1:
                continue
            missing = [s for s in group if s.owner != self.player.name]
            if not missing:
                continue
            target = missing[0]
            if target.owner == 'Bank':
                continue
            recipient = next((p for p in game.players if p.name == target.owner), None)
            if recipient is None:
                continue

            # EasyBot can offer ANY unimproved property it owns (not just singletons)
            candidates = [
                s for s in BOARD
                if isinstance(s, Property)
                and s.owner == self.player.name
                and s.n_houses == 0
                and not s.is_mortgaged
                and s.colour != colour  # Don't offer from the colour we're trying to complete
            ]
            if not candidates:
                continue

            # Prefer the cheapest property so we give away least face value
            candidates.sort(key=lambda s: s.price)
            offer_prop = candidates[0]

            offer_side = {'cash': 0, 'properties': [offer_prop.name], 'jail_cards': 0}
            ask_side   = {'cash': 0, 'properties': [target.name],     'jail_cards': 0}

            # Self-evaluate: would I (as recipient) accept getting target for offer_prop?
            # Reframe: incoming = target (ask_side), outgoing = offer_prop (offer_side)
            if not self.evaluate_incoming_trade(ask_side, offer_side, recipient, game):
                continue

            _announce(self.player, f"Wants {target.name} — offers {offer_prop.name}.")
            bot_propose_trade(self.player, offer_side, ask_side, recipient, game)
            break



# ─────────────────────────────────────────────────────────────────────────────
# MEDIUM BOT  — "The Value Shopper"
# ─────────────────────────────────────────────────────────────────────────────

class MediumBot(BaseBot):
    tier = 'medium'

    CASH_BUILD_SAFETY  = 150
    CASH_REDEEM_FLOOR  = 600
    PRIORITY_COLOURS = {'Orange', 'Red', 'Light Blue', 'Pink'}
    MULTIPLIERS = {
        'Brown': 1.0, 'Light Blue': 1.1, 'Pink': 1.2, 
        'Orange': 1.3, 'Red': 1.4, 'Yellow': 1.5, 
        'Green': 1.6, 'Dark Blue': 1.7
    }

    def _buy_buffer(self, game):
        return evaluate_board_risk(self.player, game) + 100

    def jail_decision(self, game):
        has_monopoly = any(
            check_monopoly(s.colour, self.player.name)
            for s in BOARD if isinstance(s, Property) and s.owner == self.player.name
        )
        if has_monopoly:
            return 'card' if self.player.comm_cards else 'pay'
        if self.player.jail_turns < 2:
            return 'roll'
        return 'card' if self.player.comm_cards else 'pay'

    def should_buy(self, space, game):
        buffer = self._buy_buffer(game)
        if self.player.cash - space.price < buffer:
            return False

        if isinstance(space, Property):
            colour = space.colour
            if colour in self.PRIORITY_COLOURS:
                return True
            if colour in ('Brown', 'Dark Blue') or isinstance(space, Utility):
                if _opponent_owns_colour_count(self.player, colour, game) > 0:
                    return False
            return True
        return True

    def auction_max_bid(self, space, current_high, game):
        if isinstance(space, Property):
            owned = _colour_owned_count(self.player, space.colour)
            mult = 1.20 if owned >= 1 else 0.90
        else:
            mult = 0.90
        return min(int(space.price * mult), self.player.cash)

    def post_roll_actions(self, game):
        self._maybe_redeem(game)
        self._maybe_mortgage(game)
        self._maybe_build(game)
        self._maybe_trade(game)

    def _maybe_build(self, game):
        monopoly_props = [
            s for s in BOARD
            if isinstance(s, Property)
            and s.owner == self.player.name
            and s.is_monopolised
            and not s.is_mortgaged
            and not s.has_hotel
        ]
        monopoly_props.sort(key=lambda s: s.n_houses)

        for space in monopoly_props:
            if space.n_houses >= 3:
                continue
            if self.player.cash - space.house_cost < self.CASH_BUILD_SAFETY:
                break
            group = get_colour_group(space.colour)
            success, msg = space.build_house(group)

            if success:
                self.player.cash -= space.house_cost
                _announce(self.player, f"Builds on {space.name}: {msg}")

    def _maybe_mortgage(self, game):
        if self.player.cash >= 150:
            return
        
        def mortgage_priority(s):
            if isinstance(s, Utility): return 0
            if isinstance(s, Railroad): return 1
            if isinstance(s, Property) and not s.is_monopolised: return 2
            return 99

        candidates = sorted(
            [s for s in _unimproved_owned(self.player) if not s.is_mortgaged],
            key=mortgage_priority
        )
        for space in candidates:
            if self.player.cash >= 150 or mortgage_priority(space) == 99:
                break
            space.is_mortgaged = True
            self.player.cash += space.mortgage_price
            _announce(self.player, f"Mortgages singleton {space.name} to preserve liquidity.")

    def _maybe_redeem(self, game):
        if self.player.cash < self.CASH_REDEEM_FLOOR:
            return
        mortgaged = sorted(
            [s for s in _owned(self.player) if s.is_mortgaged],
            key=lambda s: s.redeem_price
        )
        for space in mortgaged:
            if self.player.cash - space.redeem_price < self.CASH_REDEEM_FLOOR:
                break
            space.is_mortgaged = False
            self.player.cash -= space.redeem_price
            _announce(self.player, f"Redeems {space.name} with excess capital.")

    def _calc_value(self, side, player_context):
        """Calculates value using the bot's internal multiplier logic."""
        val = side['cash']
        for p_name in side['properties']:
            space = _get_space(p_name)
            if not space: continue
            if not isinstance(space, Property):
                val += space.price
                continue
            base = space.price
            mult = self.MULTIPLIERS.get(space.colour, 1.0)
            if _colour_owned_count(player_context, space.colour) == 2:
                mult *= 2.0
            val += base * mult
        return val

    def _completes_monopoly(self, properties, player):
        """Checks if receiving these properties completes a monopoly for the player."""
        for p_name in properties:
            space = _get_space(p_name)
            if isinstance(space, Property):
                if _colour_owned_count(player, space.colour) == _colour_size(space.colour) - 1:
                    return True
        return False
    
    def _maybe_trade(self, game):
        """Propose 1-for-1 colour-completion swap when 1 property away from monopoly."""
        from trades import bot_propose_trade
        ALL_COLOURS = ['Orange', 'Red', 'Light Blue', 'Pink', 'Yellow', 'Green', 'Brown', 'Dark Blue']
        for colour in ALL_COLOURS:
            group = get_colour_group(colour)
            owned = _colour_owned_count(self.player, colour)
            size  = _colour_size(colour)
            if owned != size - 1:
                continue
            missing = [s for s in group if s.owner != self.player.name]
            if not missing:
                continue
            target = missing[0]
            if target.owner == 'Bank':
                continue
            recipient = next((p for p in game.players if p.name == target.owner), None)
            if recipient is None:
                continue
            # Find a non-monopoly property to offer in return
            offer_prop = None
            for colour2 in reversed(ALL_COLOURS):
                if colour2 == colour:
                    continue
                if check_monopoly(colour2, self.player.name):
                    continue
                candidates = [
                    s for s in get_colour_group(colour2)
                    if s.owner == self.player.name
                    and not s.is_mortgaged
                    and s.n_houses == 0
                ]
                if candidates:
                    offer_prop = candidates[0]
                    break
            if offer_prop is None or abs(offer_prop.price - target.price) > 80:
                continue
            offer_side = {'cash': 0, 'properties': [offer_prop.name], 'jail_cards': 0}
            ask_side   = {'cash': 0, 'properties': [target.name],     'jail_cards': 0}

            # Self-evaluate: would I accept getting target for offer_prop?
            # (incoming = target/ask_side, outgoing = offer_prop/offer_side from bot's perspective)
            if not self.evaluate_incoming_trade(ask_side, offer_side, recipient, game):
                continue

            _announce(self.player, f"Proposes trade: {offer_prop.name} for {target.name}.")
            bot_propose_trade(self.player, offer_side, ask_side, recipient, game)
            break  # one trade attempt per turn
        
    def evaluate_incoming_trade(self, offer_side, ask_side, initiator, game):
        incoming_val = self._calc_value(offer_side, self.player)
        outgoing_val = self._calc_value(ask_side, self.player)
        
        if self._completes_monopoly(offer_side['properties'], self.player):
            return incoming_val > outgoing_val
            
        if outgoing_val == 0:
            return incoming_val > 0
            
        return incoming_val >= 2.0 * outgoing_val
        
    # In bots.py inside the MediumBot class
    def generate_counter_offer(self, human_offer, human_ask, human_player, game):
        incoming_val = self._calc_value(human_offer, self.player)
        outgoing_val = self._calc_value(human_ask, self.player)

        completes_mine  = self._completes_monopoly(human_offer['properties'], self.player)
        completes_theirs = self._completes_monopoly(human_ask['properties'], human_player)

        if completes_theirs:
            return None  # Hard reject — never help complete an opponent's monopoly via counter

        if completes_mine:
            threshold = outgoing_val + 1
        else:
            threshold = 2.0 * outgoing_val

        if incoming_val >= threshold:
            return None  # Already meets our bar — shouldn't reach here

        shortfall = threshold - incoming_val

        # Base counter: mirror the human's positions
        bot_offer_cash  = human_ask['cash']
        bot_offer_props = list(human_ask['properties'])
        bot_ask_cash    = human_offer['cash']
        bot_ask_props   = list(human_offer['properties'])

        # Tier-1 & Tier-2 = first 20 board positions: Brown, Light Blue, Pink, Orange
        LOW_TIER = {'Brown', 'Light Blue', 'Pink', 'Orange'}

        if completes_mine:
            # 1) Sweeten with extra cash (up to 35 % of reserves)
            extra_cash = min(int(self.player.cash * 0.35), int(shortfall))
            bot_offer_cash += extra_cash
            shortfall -= extra_cash

            # 2) Add low-tier properties to the offer to close remaining gap
            if shortfall > 0:
                sweeteners = sorted(
                    [
                        s for s in BOARD
                        if isinstance(s, Property)
                        and s.owner == self.player.name
                        and s.n_houses == 0
                        and not s.is_mortgaged
                        and s.colour in LOW_TIER
                        and s.name not in bot_offer_props
                        and s.name not in human_ask['properties']
                    ],
                    key=lambda s: self._calc_value(
                        {'cash': 0, 'properties': [s.name], 'jail_cards': 0}, self.player
                    ),
                )
                for prop in sweeteners:
                    if shortfall <= 0:
                        break
                    prop_val = self._calc_value(
                        {'cash': 0, 'properties': [prop.name], 'jail_cards': 0}, self.player
                    )
                    bot_offer_props.append(prop.name)
                    shortfall -= prop_val

            # 3) Whatever shortfall remains: ask the human to chip in cash
            if shortfall > 0:
                bot_ask_cash = human_offer['cash'] + int(shortfall)
        else:
            # Non-monopoly counter: simply ask the human for more cash
            bot_ask_cash = human_offer['cash'] + int(shortfall)

        bot_offer = {'cash': bot_offer_cash, 'properties': bot_offer_props, 'jail_cards': human_ask['jail_cards']}
        bot_ask   = {'cash': bot_ask_cash,   'properties': bot_ask_props,   'jail_cards': human_offer['jail_cards']}

        if human_player.cash >= bot_ask['cash']:
            return {'offer_side': bot_offer, 'ask_side': bot_ask}
        return None


# ─────────────────────────────────────────────────────────────────────────────
# HARD BOT  — "The Shark"
# ─────────────────────────────────────────────────────────────────────────────

class HardBot(BaseBot):
    tier = 'hard'
    MULTIPLIERS = {
        'Brown': 1.0, 'Light Blue': 1.2, 'Pink': 1.4, 'Orange': 1.6,
        'Red': 1.8, 'Yellow': 2.0, 'Green': 2.2, 'Dark Blue': 2.4
    }

    def _get_game_phase(self):
        unowned_props = [s for s in BOARD if isinstance(s, (Property, Railroad, Utility)) and s.owner == 'Bank']
        return "early" if len(unowned_props) > 6 else "late"

    def jail_decision(self, game):
        if self._get_game_phase() == "early":
            return 'card' if self.player.comm_cards else 'pay'
        return 'roll' # Stay safe in jail during late game

    def should_buy(self, space, game):
        # Rule: Drops buffer to $0 if it completes a monopoly or denies an opponent
        is_monopoly_filler = _colour_owned_count(self.player, getattr(space, 'colour', '')) == _colour_size(getattr(space, 'colour', '')) - 1
        is_denial_buy = _opponent_owns_colour_count(self.player, getattr(space, 'colour', ''), game) == _colour_size(getattr(space, 'colour', '')) - 1
        
        if is_monopoly_filler or is_denial_buy:
            return self.player.cash >= space.price
            
        # Standard conservative buying buffer
        return (self.player.cash - space.price) >= evaluate_board_risk(self.player, game)

    def auction_max_bid(self, space, current_high, game):
        colour = getattr(space, 'colour', '')
        # Bleed opponents looking to complete sets
        if _opponent_owns_colour_count(self.player, colour, game) == _colour_size(colour) - 1:
            return min(int(space.price * 1.6), self.player.cash)
        if _colour_owned_count(self.player, colour) == _colour_size(colour) - 1:
            return min(int(space.price * 1.3), self.player.cash)
        return min(int(space.price * 0.9), self.player.cash)

    def post_roll_actions(self, game):
        self._aggressive_liquidation(game)
        self._house_shortage_build(game)
        self._maybe_trade(game)

    def _house_shortage_build(self, game):
        """Builds to 4 houses on lower/mid sets, intentionally refusing to upgrade to hotels."""
        monopoly_props = [
            s for s in BOARD
            if isinstance(s, Property) and s.owner == self.player.name and s.is_monopolised and not s.is_mortgaged
        ]
        # Target high traffic/efficient properties first (Oranges, Reds, Light Blues)
        monopoly_props.sort(key=lambda s: s.house_cost)

        for space in monopoly_props:
            while space.n_houses < 4 and not space.has_hotel:
                if self.player.cash >= space.house_cost and _bank_houses_available() > 0:
                    group = get_colour_group(space.colour)
                    success, msg = space.build_house(group)

                    if success:
                        self.player.cash -= space.house_cost
                        _announce(self.player, f"Locking house layer on {space.name}: {msg}")
                    else:
                        break
                else:
                    break

    def _aggressive_liquidation(self, game):
        """Liquidates dead singletons instantly if cash is tight and a live monopoly can be expanded."""
        has_monopoly = any(s.is_monopolised for s in _owned(self.player, Property))
        if not has_monopoly or self.player.cash >= 200:
            return

        singletons = [s for s in _unimproved_owned(self.player) if isinstance(s, Property) and not s.is_monopolised and not s.is_mortgaged]
        for space in singletons:
            space.is_mortgaged = True
            self.player.cash += space.mortgage_price
            _announce(self.player, f"Shark liquidation: Mortgaging dead asset {space.name} to fund monopolies.")

    def _calc_value(self, side, player_context):
        val = side['cash']
        for p_name in side['properties']:
            space = _get_space(p_name)
            if not space: continue
            if not isinstance(space, Property):
                val += space.price
                continue
            base = space.price
            mult = self.MULTIPLIERS.get(space.colour, 1.0)
            if _colour_owned_count(player_context, space.colour) == 2:
                mult *= 2.0
            val += base * mult
        return val
    
    def _completes_monopoly(self, properties, player):
        for p_name in properties:
            space = _get_space(p_name)
            if isinstance(space, Property):
                if _colour_owned_count(player, space.colour) == _colour_size(space.colour) - 1:
                    return True
        return False
        
        
    def _maybe_trade(self, game):
        """
        EV-based trade proposals. Two strategies:
        1) Standard monopoly-completing swap, possibly with cash-over-top
        2) Extortion: offer a low-value prop to a cash-strapped opponent
           who needs our singleton, demanding their near-monopoly piece back
        """
        from trades import bot_propose_trade
        COLOUR_PRIORITY = ['Orange', 'Red', 'Light Blue', 'Pink', 'Yellow', 'Green', 'Brown', 'Dark Blue']

        for colour in COLOUR_PRIORITY:
            group = get_colour_group(colour)
            owned = _colour_owned_count(self.player, colour)
            size  = _colour_size(colour)
            if owned != size - 1:
                continue
            missing = [s for s in group if s.owner != self.player.name]
            if not missing:
                continue
            target = missing[0]
            if target.owner == 'Bank':
                continue
            recipient = next((p for p in game.players if p.name == target.owner), None)
            if recipient is None:
                continue

            # Find bait property from low-priority colour
            offer_prop = None
            for colour2 in reversed(COLOUR_PRIORITY):
                if colour2 == colour:
                    continue
                if check_monopoly(colour2, self.player.name):
                    continue
                candidates = [
                    s for s in get_colour_group(colour2)
                    if s.owner == self.player.name
                    and not s.is_mortgaged
                    and s.n_houses == 0
                ]
                if candidates:
                    offer_prop = candidates[0]
                    break

            # Demand cash-over-top if our bait is cheaper than target
            cash_top = 0
            if offer_prop and offer_prop.price < target.price:
                cash_top = min(
                    int((target.price - offer_prop.price) * 0.75),
                    self.player.cash // 4
                )

            if offer_prop:
                offer_side = {'cash': cash_top, 'properties': [offer_prop.name], 'jail_cards': 0}
            elif self.player.cash >= 700:
                cash_offer = min(int(target.price * 1.2), self.player.cash - 400)
                offer_side = {'cash': cash_offer, 'properties': [], 'jail_cards': 0}
            else:
                continue

            ask_side = {'cash': 0, 'properties': [target.name], 'jail_cards': 0}

            # Self-evaluate: would I (as recipient) accept getting target for what I'm offering?
            # (incoming = target/ask_side, outgoing = offer_side from bot's perspective)
            if not self.evaluate_incoming_trade(ask_side, offer_side, recipient, game):
                continue

            _announce(self.player, f"Shark proposes trade for {target.name}.")
            bot_propose_trade(self.player, offer_side, ask_side, recipient, game)
            break

    def evaluate_incoming_trade(self, offer_side, ask_side, initiator, game):
        incoming_val = self._calc_value(offer_side, self.player)
        outgoing_val = self._calc_value(ask_side, self.player)
        
        completes_mine = self._completes_monopoly(offer_side['properties'], self.player)
        completes_theirs = self._completes_monopoly(ask_side['properties'], initiator)
        
        if completes_theirs:
            # Rule: Refuse to give them a monopoly unless down on cash (<200) and given 3x value
            if self.player.cash < 200:
                return incoming_val >= 3.0 * outgoing_val
            return False
            
        if completes_mine:
            return incoming_val >= 1.0 * outgoing_val
            
        if outgoing_val == 0:
            return incoming_val > 0
        return incoming_val >= 1.5 * outgoing_val # Default shark baseline for non-monopoly trades
    
    # In bots.py inside the HardBot class
    def generate_counter_offer(self, human_offer, human_ask, human_player, game):
        incoming_val = self._calc_value(human_offer, self.player)
        outgoing_val = self._calc_value(human_ask, self.player)

        completes_mine   = self._completes_monopoly(human_offer['properties'], self.player)
        completes_theirs = self._completes_monopoly(human_ask['properties'], human_player)

        if completes_theirs:
            if self.player.cash < 200:
                target_incoming = 3.0 * outgoing_val
            else:
                return None  # Hard rejection — will not negotiate handing over a monopoly

        elif completes_mine:
            target_incoming = 1.0 * outgoing_val
        else:
            target_incoming = 1.5 * outgoing_val

        if incoming_val >= target_incoming:
            return None

        shortfall = target_incoming - incoming_val

        # Base counter: mirror the human's positions
        bot_offer_cash  = human_ask['cash']
        bot_offer_props = list(human_ask['properties'])
        bot_ask_cash    = human_offer['cash']
        bot_ask_props   = list(human_offer['properties'])

        # High-tier targets: Yellow, Green, Dark Blue
        HIGH_TIER = {'Yellow', 'Green', 'Dark Blue'}
        # Low-tier property sweeteners the Shark is willing to part with
        LOW_TIER  = {'Brown', 'Light Blue', 'Pink'}

        targeting_high_tier = any(
            _get_space(p) is not None and isinstance(_get_space(p), Property)
            and _get_space(p).colour in HIGH_TIER
            for p in human_offer['properties']
        )

        if completes_mine and targeting_high_tier:
            # 1) Sweeten with extra cash — up to 45 % of reserves
            extra_cash = min(int(self.player.cash * 0.45), int(shortfall))
            bot_offer_cash += extra_cash
            shortfall -= extra_cash

            # 2) Throw in low-tier properties to close any remaining gap
            if shortfall > 0:
                sweeteners = sorted(
                    [
                        s for s in BOARD
                        if isinstance(s, Property)
                        and s.owner == self.player.name
                        and s.n_houses == 0
                        and not s.is_mortgaged
                        and s.colour in LOW_TIER
                        and s.name not in bot_offer_props
                        and s.name not in human_ask['properties']
                    ],
                    key=lambda s: self._calc_value(
                        {'cash': 0, 'properties': [s.name], 'jail_cards': 0}, self.player
                    ),
                )
                for prop in sweeteners:
                    if shortfall <= 0:
                        break
                    prop_val = self._calc_value(
                        {'cash': 0, 'properties': [prop.name], 'jail_cards': 0}, self.player
                    )
                    bot_offer_props.append(prop.name)
                    shortfall -= prop_val

            # 3) Any leftover shortfall: ask the human for more cash
            if shortfall > 0:
                bot_ask_cash = human_offer['cash'] + int(shortfall)

        elif completes_mine:
            # Non-high-tier monopoly: still a bit generous with cash (up to 25 %)
            extra_cash = min(int(self.player.cash * 0.25), int(shortfall))
            bot_offer_cash += extra_cash
            shortfall -= extra_cash
            if shortfall > 0:
                bot_ask_cash = human_offer['cash'] + int(shortfall)
        else:
            # Standard: just ask the human for more cash
            bot_ask_cash = human_offer['cash'] + int(shortfall)

        bot_offer = {'cash': bot_offer_cash, 'properties': bot_offer_props, 'jail_cards': human_ask['jail_cards']}
        bot_ask   = {'cash': bot_ask_cash,   'properties': bot_ask_props,   'jail_cards': human_offer['jail_cards']}

        if human_player.cash >= bot_ask['cash']:
            return {'offer_side': bot_offer, 'ask_side': bot_ask}
        return None


    

BOT_NAMES = {
    'easy': [
        'Rookie', 'Bumble', 'Dizzy', 'Clumsy', 'Pudding',
        'Wobble', 'Breezy', 'Dopey', 'Fumble', 'Noodle',
    ],
    'medium': [
        'Sterling', 'Hawke', 'Vera', 'Marlowe', 'Cassidy',
        'Quinn', 'Reeve', 'Darcy', 'Monroe', 'Sloane',
    ],
    'hard': [
        'Magnus', 'Cipher', 'Vortex', 'Axiom', 'Nemesis',
        'Oracle', 'Titan', 'Specter', 'Apex', 'Dread',
    ],
}
