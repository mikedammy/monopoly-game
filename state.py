import time
from objects import (
    Player, Dice,
    Property, Railroad, Utility,
    Go, Tax, FreeParking, GoToJail, Jail,
    CommunityChest, Chance,
    STARTING_CASH
)
from board import (
    BOARD, jail,
    check_monopoly, get_colour_group,
    get_railroad_count, get_utility_count,
    nearest_railroad, nearest_utility
)

#------------------------------------------------------
# GAME STATE
#------------------------------------------------------

class GameState:

    MAX_JAIL_TURNS = 3
    JAIL_FINE = 50

    def __init__(self, player_names):
        if not 2 <= len(player_names) <= 8:
            raise ValueError("Monopoly requires 2–8 players.")
        if len(player_names) != len(set(player_names)):
            raise ValueError("Player names must be unique.")

        self.players = [Player(name) for name in player_names]
        self.board = BOARD
        self.jail = jail

        self.turn_index = 0          # whose turn it is
        self.doubles_streak = 0      # consecutive doubles this turn
        self.round_number = 1
        self.active = True           # False when game ends

        self.logs = []
        self._log(f"Game started with players: {player_names}")

    # --------------------------------------------------
    # LOGGING
    # --------------------------------------------------

    def _log(self, msg):
        self.logs.append(msg)
        print(msg)
        time.sleep(0.9)

    # --------------------------------------------------
    # TURN MANAGEMENT
    # --------------------------------------------------

    @property
    def current_player(self):
        return self.players[self.turn_index]

    def next_turn(self):
        """Advance to the next active player, skipping eliminated ones."""
        self.doubles_streak = 0
        self.turn_index = (self.turn_index + 1) % len(self.players)
        # If we've wrapped back to player 0, increment round
        if self.turn_index == 0:
            self.round_number += 1
            self._log(f"--- Round {self.round_number} ---")
        # Skip eliminated players (cash < 0 handled at bankruptcy)
        while not self._is_active(self.current_player):
            self.turn_index = (self.turn_index + 1) % len(self.players)

    def _is_active(self, player):
        return player in self.players  # eliminated players are removed from list

    # --------------------------------------------------
    # ROLLING AND MOVING
    # --------------------------------------------------

    def take_turn(self):
        """Execute a full turn for the current player. Returns a summary dict."""
        player = self.current_player
        self._log(f"\n{player.name}'s turn (Round {self.round_number})")

        # Jailed player special flow
        if player.jailed:
            return self._take_jail_turn(player)

        d1, d2, total, is_double = Dice.roll()
        self._log(f"  Rolled {d1} + {d2} = {total} {'(Double!)' if is_double else ''}")

        if is_double:
            self.doubles_streak += 1
            if self.doubles_streak == 3:
                self._log(f"  {player.name} rolled 3 consecutive doubles — Go to Jail!")
                self._send_to_jail(player)
                return {'action': 'go_to_jail', 'reason': 'speeding'}

        passed_go = player.move(total)
        if passed_go and not player.jailed:
            Go.pay_salary(player)
            self._log(f"  {player.name} passed Go — collected $200. Cash: ${player.cash}")

        result = self._resolve_space(player, dice_total=total)

        # Purchase decision is pending — don't advance turn yet.
        # game.py will call next_turn() after the decision is resolved.
        if result.get('action') == 'purchase_decision':
            if is_double:
                result['extra_roll'] = True
            return result

        # Doubles let you roll again — but NOT if the player ended up in jail
        # (sent by a card or Go To Jail space during this turn)
        if is_double and not player.jailed:
            self._log(f"  {player.name} gets another roll (doubles).")
            return {**result, 'extra_roll': True}

        return result

    def _take_jail_turn(self, player):
        """Handle a turn while the player is in jail."""
        player.jail_turns += 1
        d1, d2, total, is_double = Dice.roll()
        self._log(f"  {player.name} is in jail (turn {player.jail_turns}). Rolled {d1}+{d2}.")

        if is_double:
            self._log(f"  Rolled doubles — {player.name} is released from jail!")
            self.jail.release(player)
            self.doubles_streak = 0   # doubles from jail don't grant extra roll
            passed_go = player.move(total)
            if passed_go:
                Go.pay_salary(player)
            result = self._resolve_space(player, dice_total=total)
            return result  # game.py calls next_turn() via end turn

        if player.jail_turns >= self.MAX_JAIL_TURNS:
            self._log(f"  {player.name} has served 3 turns — must pay ${self.JAIL_FINE} fine.")
            player.cash -= self.JAIL_FINE
            self.jail.release(player)
            passed_go = player.move(total)
            if passed_go:
                Go.pay_salary(player)
            result = self._resolve_space(player, dice_total=total)
            return result  # game.py calls next_turn() via end turn

        self._log(f"  {player.name} stays in jail.")
        return {'action': 'in_jail', 'turns_served': player.jail_turns}

    # --------------------------------------------------
    # SPACE RESOLUTION
    # --------------------------------------------------

    def _resolve_space(self, player, dice_total=None):
        space = self.board[player.position]
        name = getattr(space, 'name', type(space).__name__)
        self._log(f"  {player.name} lands on: {name}")

        if isinstance(space, Go):
            return {'action': 'go', 'space': name}

        if isinstance(space, Tax):
            space.collect(player)
            self._log(f"  {player.name} paid {space.name}: ${space.amount}. Cash: ${player.cash}")
            return {'action': 'tax', 'space': name, 'amount': space.amount}

        if isinstance(space, FreeParking):
            return {'action': 'free_parking', 'space': name}

        if isinstance(space, GoToJail):
            self._send_to_jail(player)
            return {'action': 'go_to_jail', 'space': name}

        if isinstance(space, Jail):
            # Just visiting
            return {'action': 'just_visiting', 'space': name}

        if isinstance(space, CommunityChest):
            old_pos = player.position
            card = CommunityChest.draw(
                player,
                all_players=self.players,
                board=self.board,
                jail=self.jail
            )
            self._handle_card_moves(player, card, space_type='community_chest')
            # If the card moved the player, resolve the new space
            if player.position != old_pos and card not in ('go to jail',):
                return self._resolve_space(player, dice_total=dice_total)
            return {'action': 'community_chest', 'card': card}

        if isinstance(space, Chance):
            old_pos = player.position
            card = Chance.draw(
                player,
                all_players=self.players,
                board=self.board,
                jail=self.jail
            )
            
            # Capture the flag to see if the card already charged rent
            rent_handled = self._handle_card_moves(player, card, space_type='chance', dice_total=dice_total)
            
            # If the card moved the player, resolve the new space
            if player.position != old_pos and card not in ('go to jail',):
                if rent_handled:
                    return {'action': 'chance_rent_paid', 'card': card}
                else:
                    return self._resolve_space(player, dice_total=dice_total)
                    
            return {'action': 'chance', 'card': card}

        if isinstance(space, Property):
            return self._resolve_property(player, space)

        if isinstance(space, Railroad):
            return self._resolve_railroad(player, space)

        if isinstance(space, Utility):
            return self._resolve_utility(player, space, dice_total)

        return {'action': 'unknown', 'space': name}

    def _resolve_property(self, player, space):
        if space.is_mortgaged:
            self._log(f"  {space.name} is mortgaged — no rent due.")
            return {'action': 'mortgaged', 'space': space.name}

        if space.owner == 'Bank':
            return self._offer_purchase(player, space)

        if space.owner == player.name:
            self._log(f"  {player.name} owns {space.name} — no rent.")
            return {'action': 'own_property', 'space': space.name}

        # Someone else owns it — pay rent
        owner = self._get_player(space.owner)
        rent = space.rent
        self._log(f"  {player.name} pays ${rent} rent to {owner.name} for {space.name}.")
        self._collect_rent(player, owner, rent, space.name)
        return {'action': 'rent_paid', 'space': space.name, 'amount': rent, 'to': owner.name}

    def _resolve_railroad(self, player, space):
        if space.is_mortgaged:
            return {'action': 'mortgaged', 'space': space.name}

        if space.owner == 'Bank':
            return self._offer_purchase(player, space)

        if space.owner == player.name:
            return {'action': 'own_property', 'space': space.name}

        owner = self._get_player(space.owner)
        count = get_railroad_count(owner.name)
        space.rent = count           # updates rent to correct tier
        rent = space.rent
        self._log(f"  {player.name} pays ${rent} rent to {owner.name} for {space.name}.")
        self._collect_rent(player, owner, rent, space.name)
        return {'action': 'rent_paid', 'space': space.name, 'amount': rent, 'to': owner.name}

    def _resolve_utility(self, player, space, dice_total):
        if space.is_mortgaged:
            return {'action': 'mortgaged', 'space': space.name}

        if space.owner == 'Bank':
            return self._offer_purchase(player, space)

        if space.owner == player.name:
            return {'action': 'own_property', 'space': space.name}

        owner = self._get_player(space.owner)
        count = get_utility_count(owner.name)
        space.rent_mult = 10 if count == 2 else 4
        rent = space.rent_due(dice_total)
        self._log(f"  {player.name} pays ${rent} rent to {owner.name} for {space.name} ({space.rent_mult}×{dice_total}).")
        self._collect_rent(player, owner, rent, space.name)
        return {'action': 'rent_paid', 'space': space.name, 'amount': rent, 'to': owner.name}

    # --------------------------------------------------
    # PURCHASE AND AUCTION
    # --------------------------------------------------

    def _offer_purchase(self, player, space):
        """
        Returns a pending decision dict. The game loop (or UI) must call
        confirm_purchase(player, space) or start_auction(space).
        """
        self._log(f"  {space.name} is unowned. Cost: ${space.price}. {player.name} may buy or pass.")
        return {
            'action': 'purchase_decision',
            'space': space.name,
            'price': space.price,
            'player': player.name
        }

    def confirm_purchase(self, player, space):
        """Call this when the player decides to buy."""
        if player.cash < space.price:
            self._log(f"  {player.name} cannot afford {space.name}.")
            return False

        player.cash -= space.price
        space.owner = player           # triggers owner.setter log
        player.properties = space.name

        self._log(f"  {player.name} bought {space.name} for ${space.price}. Cash: ${player.cash}")
        self._check_and_set_monopoly(player, space)
        self._update_railroad_rents(player)
        self._update_utility_mults(player)
        return True

    def complete_auction_purchase(self, winner, space, winning_bid):
        """
        Called by game.py after the English auction resolves.
        Transfers ownership and updates all dependent state.
        """
        winner.cash -= winning_bid
        space.owner = winner
        winner.properties = space.name
        self._log(f"  {winner.name} wins auction for {space.name} at ${winning_bid}. Cash: ${winner.cash}")
        self._check_and_set_monopoly(winner, space)
        self._update_railroad_rents(winner)
        self._update_utility_mults(winner)

    # --------------------------------------------------
    # MONOPOLY AND RENT UPDATES
    # --------------------------------------------------

    def _check_and_set_monopoly(self, player, space):
        """After a purchase, check if a colour group is now monopolised."""
        if not isinstance(space, Property):
            return

        colour = space.colour
        if check_monopoly(colour, player.name):
            group = get_colour_group(colour)
            for prop in group:
                if not prop.is_monopolised:
                    prop.is_monopolised = True
            self._log(f"  {player.name} has a MONOPOLY on {colour}!")

    def _update_railroad_rents(self, player):
        """After any railroad purchase, update rent tiers for all player's railroads."""
        count = get_railroad_count(player.name)
        for space in self.board:
            if isinstance(space, Railroad) and space.owner == player.name:
                space.rent = count

    def _update_utility_mults(self, player):
        """After any utility purchase, update multiplier for all player's utilities."""
        count = get_utility_count(player.name)
        mult = 10 if count == 2 else 4
        for space in self.board:
            if isinstance(space, Utility) and space.owner == player.name:
                space.rent_mult = mult

    # --------------------------------------------------
    # CARD MOVE HANDLING
    # --------------------------------------------------

    def _handle_card_moves(self, player, card, space_type, dice_total=None):
        """
        Handles board movements from cards. 
        Returns True if the card explicitly handled rent payment, False otherwise.
        """
        rent_handled = False
        
        if card == 'go back three':
            new_pos = (player.position - 3) % 40
            player.position = new_pos

        elif card == 'advance to nearest railroad':
            space, pos = nearest_railroad(player.position)
            old_pos = player.position
            player.position = pos
            if pos < old_pos:
                Go.pay_salary(player)
                self._log(f"  {player.name} passed Go — collected $200. Cash: ${player.cash}")
                
            if space.owner != 'Bank' and space.owner != player.name:
                owner = self._get_player(space.owner)
                count = get_railroad_count(owner.name)
                space.rent = count
                rent = space.rent * 2   # Chance card rule: pay double rent
                self._log(f"  Advance to nearest railroad — {player.name} pays double rent: ${rent}")
                self._collect_rent(player, owner, rent, space.name)
                rent_handled = True

        elif card == 'advance to nearest utility':
            space, pos = nearest_utility(player.position)
            old_pos = player.position
            player.position = pos
            if pos < old_pos:
                Go.pay_salary(player)
                self._log(f"  {player.name} passed Go — collected $200. Cash: ${player.cash}")
                
            if space.owner != 'Bank' and space.owner != player.name:
                owner = self._get_player(space.owner)
                if dice_total:
                    space.rent_mult = 10
                    rent = space.rent_due(dice_total)
                    self._log(f"  Advance to nearest utility — {player.name} pays 10×{dice_total} = ${rent}")
                    self._collect_rent(player, owner, rent, space.name)
                    rent_handled = True
                    
        return rent_handled


    # --------------------------------------------------
    # RENT COLLECTION AND BANKRUPTCY
    # --------------------------------------------------

    def _collect_rent(self, payer, owner, amount, space_name):
        """Collect rent, triggering bankruptcy if payer can't afford it."""
        if payer.cash >= amount:
            payer.pay_rent(owner, amount)
        else:
            self._log(f"  {payer.name} can't afford ${amount} rent — attempting liquidation.")
            self._handle_insolvency(payer, owner, amount)

    def _handle_insolvency(self, debtor, creditor, amount):
    # Step 1: sell all houses and hotels down to bare properties safely
        while debtor.cash < amount:
            improved = [s for s in self.board if isinstance(s, Property) and s.owner == debtor.name and s.n_houses > 0]
            if not improved:
                break
            # Sort descending by n_houses to naturally satisfy the even-sell rule
            improved.sort(key=lambda x: x.n_houses, reverse=True)
            target = improved[0]
            group = get_colour_group(target.colour)
            
            success, sell_val, msg = target.sell_house(group)
            if success:
                debtor.cash += sell_val
            else:
                break # Safety break to prevent infinite loops

        # Step 2: mortgage unimproved properties
        for space in self.board:
            if isinstance(space, (Property, Railroad, Utility)) and space.owner == debtor.name:
                if not space.is_mortgaged and debtor.cash < amount:
                    space.is_mortgaged = True
                    debtor.cash += space.mortgage_price
                    self._log(f"  {debtor.name} mortgaged {space.name} for ${space.mortgage_price}.")

        if debtor.cash >= amount:
            debtor.pay_rent(creditor, amount)
            self._log(f"  {debtor.name} covered the debt after liquidation.")
        else:
            self._declare_bankruptcy(debtor, creditor)


    def _declare_bankruptcy(self, debtor, creditor):
        self._log(f"  {debtor.name} is BANKRUPT!")

        if creditor is None:
            # Bankrupt to the bank — all assets go back to bank
            for space in self.board:
                if isinstance(space, (Property, Railroad, Utility)) and space.owner == debtor.name:
                    space.reset()
            self._log(f"  All of {debtor.name}'s properties return to the Bank for auction.")
        else:
            # Bankrupt to a player — all assets transfer
            for space in self.board:
                if isinstance(space, (Property, Railroad, Utility)) and space.owner == debtor.name:
                    space.owner = creditor   # transfer ownership
                    creditor.properties = space.name
                    # Creditor must pay 10% interest on any mortgaged property received
                    if space.is_mortgaged:
                        interest = int(space.mortgage_price * 0.10)
                        creditor.cash -= interest
                        self._log(f"  {creditor.name} pays ${interest} interest on mortgaged {space.name}.")
                    # Re-check monopolies for new owner
                    if isinstance(space, Property):
                        self._check_and_set_monopoly(creditor, space)
            self._update_railroad_rents(creditor)
            self._update_utility_mults(creditor)
            creditor.cash += debtor.cash   # remaining cash transfers too
            self._log(f"  {debtor.name}'s assets transferred to {creditor.name}.")

        self.players.remove(debtor)
        self._log(f"  {debtor.name} has been eliminated.")
        self._check_win_condition()

    # --------------------------------------------------
    # JAIL HELPERS
    # --------------------------------------------------

    def _send_to_jail(self, player):
        player.position = 10
        self.jail.add_prisoner(player)
        self._log(f"  {player.name} sent to Jail.")

    def pay_jail_fine(self, player):
        """Player voluntarily pays $50 to leave jail before rolling."""
        if not player.jailed:
            self._log(f"  {player.name} is not in jail.")
            return False
        if player.cash < self.JAIL_FINE:
            self._log(f"  {player.name} can't afford the ${self.JAIL_FINE} fine.")
            return False
        player.cash -= self.JAIL_FINE
        self.jail.release(player)
        self._log(f"  {player.name} paid ${self.JAIL_FINE} fine and is free.")
        return True

    def use_jail_card(self, player):
        """Player uses a Get Out of Jail Free card."""
        if player.use_jail_card():
            self.jail.release(player)
            self._log(f"  {player.name} used a Get Out of Jail Free card.")
            return True
        self._log(f"  {player.name} has no Get Out of Jail Free card.")
        return False

    # --------------------------------------------------
    # WIN CONDITION
    # --------------------------------------------------

    def _check_win_condition(self):
        if len(self.players) == 1:
            winner = self.players[0]
            self._log(f"\n{'='*40}")
            self._log(f"  {winner.name} WINS THE GAME!")
            self._log(f"  Final cash: ${winner.cash}")
            self._log(f"{'='*40}")
            self.active = False

    # --------------------------------------------------
    # STATUS HELPERS
    # --------------------------------------------------

    def _get_player(self, name):
        for p in self.players:
            if p.name == name:
                return p
        raise ValueError(f"Player '{name}' not found.")

    def standings(self):
        """Print current cash standings for all active players."""
        from board import BOARD as _BOARD
        print("\n--- Standings ---")
        ranked = sorted(self.players, key=lambda p: p.net_worth(self.board), reverse=True)
        for i, p in enumerate(ranked, 1):
            space_name = getattr(_BOARD[p.position], 'name', f'Space {p.position}')
            jail_tag   = " [JAIL]" if p.jailed else ""
            bot_tag    = f" [BOT/{p._bot.tier.upper()}]" if hasattr(p, '_bot') else ""
            print(f"  {i}. {p.name}{bot_tag} — Cash: ${p.cash} | Net worth: ${p.net_worth(self.board)} | Pos: [{p.position:02d}] {space_name}{jail_tag}")
        print()

    def __repr__(self):
        return (f"GameState(round={self.round_number}, "
                f"turn={self.current_player.name}, "
                f"players={[p.name for p in self.players]})")
