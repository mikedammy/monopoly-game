"""
trades.py — Player-to-player trade negotiation.

Flow:
  1. Initiator picks a recipient
  2. Initiator browses recipient's assets and picks what they WANT (ask side)
  3. Initiator then builds what they're offering in return (offer side)
  4. Full offer is shown to recipient who can accept, counter, or reject
  5. Counter-offer flips roles and loops
"""

import time
from objects import Property, Railroad, Utility

SLEEP = 0.5


def sleep():
    time.sleep(SLEEP)


def divider(char='─', width=50):
    print(char * width)


# ─────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────

def _owned_tradeable(player, board):
    """Unimproved properties owned by player (including mortgaged)."""
    return [
        s for s in board
        if isinstance(s, (Property, Railroad, Utility))
        and s.owner == player.name
        and (not isinstance(s, Property) or s.n_houses == 0)
        # Removed the "and not s.is_mortgaged" check
    ]


def _get_space(name, board):
    return next((s for s in board if getattr(s, 'name', None) == name), None)


def _show_player_assets(player, board):
    """Print a readable summary of what a player owns — so the initiator can browse."""
    tradeable = _owned_tradeable(player, board)
    divider()
    print(f"  {player.name}'s assets  (cash: ${player.cash})")
    if tradeable:
        for i, s in enumerate(tradeable, 1):
            colour = f" [{s.colour}]" if isinstance(s, Property) else ""
            print(f"    {i}. {s.name}{colour}  (face value ${s.price})")
    else:
        print("    (no tradeable properties)")
    if player.comm_cards:
        print(f"    + {len(player.comm_cards)} Get Out of Jail Free card(s)")
    divider()
    sleep()


def _print_offer(offer_side, ask_side, initiator, recipient):
    divider()
    print(f"  TRADE SUMMARY")
    print(f"  {initiator.name} gives:")
    print(f"    Cash       : ${offer_side['cash']}")
    if offer_side['properties']:
        print(f"    Properties : {', '.join(offer_side['properties'])}")
    if offer_side['jail_cards'] > 0:
        print(f"    Jail cards : {offer_side['jail_cards']}")
    print(f"  {recipient.name} gives:")
    print(f"    Cash       : ${ask_side['cash']}")
    if ask_side['properties']:
        print(f"    Properties : {', '.join(ask_side['properties'])}")
    if ask_side['jail_cards'] > 0:
        print(f"    Jail cards : {ask_side['jail_cards']}")
    divider()
    sleep()


def _validate_side(side, player, board):
    """Returns (True, '') or (False, reason)."""
    if side['cash'] < 0:
        return False, "Cash amount can't be negative."
    if side['cash'] > player.cash:
        return False, f"{player.name} only has ${player.cash}."
    owned_names = {s.name for s in _owned_tradeable(player, board)}
    for prop in side['properties']:
        if prop not in owned_names:
            return False, f"{player.name} doesn't own unimproved '{prop}'."
    if side['jail_cards'] > len(player.comm_cards):
        return False, f"{player.name} only has {len(player.comm_cards)} jail card(s)."
    return True, ''


def _build_ask_side(initiator, recipient, board):
    """
    Step 1: Initiator browses recipient's assets and picks what they want.
    Returns ask_side dict (what recipient gives) or None to cancel.
    """
    tradeable = _owned_tradeable(recipient, board)

    print(f"\n  Step 1 — What do you want from {recipient.name}?")
    _show_player_assets(recipient, board)

    # Cash ask
    while True:
        raw = input(f"  Cash to request from {recipient.name} (0 for none): $").strip()
        try:
            cash = int(raw) if raw else 0
            if cash < 0:
                raise ValueError
            if cash > recipient.cash:
                print(f"  {recipient.name} only has ${recipient.cash}.")
                continue
            break
        except ValueError:
            print("  Enter a non-negative whole number.")

    # Properties ask
    chosen_props = []
    if tradeable:
        print(f"\n  Which properties do you want? (numbers separated by commas, blank = none)")
        raw = input("  Properties: ").strip()
        if raw:
            for token in raw.split(','):
                token = token.strip()
                try:
                    idx = int(token) - 1
                    if 0 <= idx < len(tradeable):
                        name = tradeable[idx].name
                        if name not in chosen_props:
                            chosen_props.append(name)
                except ValueError:
                    pass

    # Jail cards ask
    jail_cards = 0
    available = len(recipient.comm_cards)
    if available > 0:
        while True:
            raw = input(f"\n  Jail-free cards to request (0–{available}): ").strip()
            try:
                jail_cards = int(raw) if raw else 0
                if 0 <= jail_cards <= available:
                    break
                print(f"  Must be 0–{available}.")
            except ValueError:
                print("  Enter a number.")

    return {'cash': cash, 'properties': chosen_props, 'jail_cards': jail_cards}


def _build_offer_side(initiator, board, ask_side, recipient):
    """
    Step 2: Initiator builds what they're offering in return.
    Returns offer_side dict or None to cancel.
    """
    tradeable = _owned_tradeable(initiator, board)

    print(f"\n  Step 2 — What will you offer {recipient.name} in return?")
    divider()
    print(f"  Your assets  (cash: ${initiator.cash})")
    if tradeable:
        for i, s in enumerate(tradeable, 1):
            colour = f" [{s.colour}]" if isinstance(s, Property) else ""
            print(f"    {i}. {s.name}{colour}  (face value ${s.price})")
    else:
        print("    (no tradeable properties)")
    if initiator.comm_cards:
        print(f"    + {len(initiator.comm_cards)} Get Out of Jail Free card(s)")
    divider()

    # Cash offer
    while True:
        raw = input(f"  Cash to offer (0 for none): $").strip()
        try:
            cash = int(raw) if raw else 0
            if cash < 0:
                raise ValueError
            if cash > initiator.cash:
                print(f"  You only have ${initiator.cash}.")
                continue
            break
        except ValueError:
            print("  Enter a non-negative whole number.")

    # Properties offer
    chosen_props = []
    if tradeable:
        print(f"\n  Which properties will you offer? (numbers, blank = none)")
        raw = input("  Properties: ").strip()
        if raw:
            for token in raw.split(','):
                token = token.strip()
                try:
                    idx = int(token) - 1
                    if 0 <= idx < len(tradeable):
                        name = tradeable[idx].name
                        if name not in chosen_props:
                            chosen_props.append(name)
                except ValueError:
                    pass

    # Jail cards offer
    jail_cards = 0
    available = len(initiator.comm_cards)
    if available > 0:
        while True:
            raw = input(f"\n  Jail-free cards to offer (0–{available}): ").strip()
            try:
                jail_cards = int(raw) if raw else 0
                if 0 <= jail_cards <= available:
                    break
                print(f"  Must be 0–{available}.")
            except ValueError:
                print("  Enter a number.")

    return {'cash': cash, 'properties': chosen_props, 'jail_cards': jail_cards}


# ─────────────────────────────────────────────────
# TRANSFER
# ─────────────────────────────────────────────────

def _execute_trade(initiator, recipient, offer_side, ask_side, board, game):
    """Transfer all assets after a trade is accepted."""
    # Cash
    initiator.cash -= offer_side['cash']
    recipient.cash += offer_side['cash']
    recipient.cash -= ask_side['cash']
    initiator.cash += ask_side['cash']

    # Properties: offer side (initiator → recipient)
    for prop_name in offer_side['properties']:
        space = _get_space(prop_name, board)
        if space:
            space.owner = recipient
            if space.name not in recipient.properties:
                recipient.properties.append(space.name)
            if prop_name in initiator.properties:
                initiator.properties.remove(prop_name)

    # Properties: ask side (recipient → initiator)
    for prop_name in ask_side['properties']:
        space = _get_space(prop_name, board)
        if space:
            space.owner = initiator
            if space.name not in initiator.properties:
                initiator.properties.append(space.name)
            if prop_name in recipient.properties:
                recipient.properties.remove(prop_name)

    # Jail cards
    for _ in range(offer_side['jail_cards']):
        if 'jail free' in initiator.comm_cards:
            initiator.comm_cards.remove('jail free')
            recipient.comm_cards.append('jail free')

    for _ in range(ask_side['jail_cards']):
        if 'jail free' in recipient.comm_cards:
            recipient.comm_cards.remove('jail free')
            initiator.comm_cards.append('jail free')

    # Update railroad / utility rent tiers for both
    game._update_railroad_rents(initiator)
    game._update_railroad_rents(recipient)
    game._update_utility_mults(initiator)
    game._update_utility_mults(recipient)

    # Re-check monopolies
    from board import get_colour_group, check_monopoly
    all_traded = offer_side['properties'] + ask_side['properties']
    for prop_name in all_traded:
        space = _get_space(prop_name, board)
        if isinstance(space, Property):
            colour = space.colour
            group  = get_colour_group(colour)
            for candidate in [initiator, recipient]:
                if check_monopoly(colour, candidate.name):
                    for p in group:
                        if not p.is_monopolised:
                            p.is_monopolised = True
                    print(f"  >> {candidate.name} now has a MONOPOLY on {colour}!")
                    break
            else:
                for p in group:
                    if p.is_monopolised:
                        p.is_monopolised = False

    print(f"\n  Trade completed: {initiator.name} ↔ {recipient.name}.")
    divider()
    sleep()


# ─────────────────────────────────────────────────
# BOT-PROPOSED TRADE HELPER
# ─────────────────────────────────────────────────

def bot_propose_trade(bot_player, offer_side, ask_side, recipient, game):
    """
    Called by bots when they want to propose a trade.
    Handles routing to bot or human recipient.
    """
    board = game.board

    ok1, r1 = _validate_side(offer_side, bot_player, board)
    ok2, r2 = _validate_side(ask_side, recipient, board)
    if not ok1 or not ok2:
        return False

    _print_offer(offer_side, ask_side, bot_player, recipient)

    if hasattr(recipient, '_bot'):
        # Bot recipient evaluates automatically
        accepted = recipient._bot.evaluate_incoming_trade(offer_side, ask_side, bot_player, game)
        if accepted:
            print(f"  [BOT/{recipient.name}] Accepts.")
            sleep()
            _execute_trade(bot_player, recipient, offer_side, ask_side, board, game)
            return True
        else:
            print(f"  [BOT/{recipient.name}] Rejects.")
            sleep()
            return False
    else:
        # ── Human recipient ──
        print(f"\n  {recipient.name}, the bot [{bot_player.name}] is offering you a trade.")
        print("    [a] Accept    [c] Counter    [r] Reject")
        while True:
            resp = input(f"  Your response [a/c/r]: ").strip().lower()
            if resp in ('a', 'c', 'r'):
                break
            print("  Enter a, c, or r.")

        if resp == 'a':
            _execute_trade(bot_player, recipient, offer_side, ask_side, board, game)
            return True

        if resp == 'r':
            print(f"  {recipient.name} rejects the bot's offer.")
            sleep()
            return False

        # ── Counter-offer negotiation loop ──
        current_bot_offer = offer_side
        current_bot_ask   = ask_side
        bot_instance      = bot_player._bot

        for round_num in range(1, 6):   # max 5 counter rounds
            divider('═')
            print(f"  Counter-offer round {round_num}  —  {recipient.name} → {bot_player.name}")
            divider('═')
            sleep()

            # Human specifies what they want from the bot
            human_counter_ask = _build_ask_side(recipient, bot_player, board)
            ok, reason = _validate_side(human_counter_ask, bot_player, board)
            if not ok:
                print(f"  Invalid ask: {reason}")
                sleep()
                return False
            if (human_counter_ask['cash'] == 0
                    and not human_counter_ask['properties']
                    and human_counter_ask['jail_cards'] == 0):
                print("  You didn't ask for anything. Counter cancelled.")
                sleep()
                return False

            # Human specifies what they're willing to offer in return
            human_counter_offer = _build_offer_side(recipient, board, human_counter_ask, bot_player)
            ok, reason = _validate_side(human_counter_offer, recipient, board)
            if not ok:
                print(f"  Invalid offer: {reason}")
                sleep()
                return False

            _print_offer(human_counter_offer, human_counter_ask, recipient, bot_player)

            # Bot evaluates the human's counter
            # EasyBot has a lenient counter-evaluation method; others use standard evaluate
            if hasattr(bot_instance, 'evaluate_counter_offer'):
                bot_accepts = bot_instance.evaluate_counter_offer(
                    human_counter_offer, human_counter_ask, recipient, game
                )
            else:
                bot_accepts = bot_instance.evaluate_incoming_trade(
                    human_counter_offer, human_counter_ask, recipient, game
                )

            if bot_accepts:
                print(f"  [BOT/{bot_player.name}] Accepts your counter-offer.")
                sleep()
                _execute_trade(recipient, bot_player, human_counter_offer, human_counter_ask, board, game)
                return True

            # Bot tries to generate a counter-counter
            print(f"  [BOT/{bot_player.name}] Not satisfied — considering a counter...")
            sleep()
            counter = bot_instance.generate_counter_offer(
                human_counter_offer, human_counter_ask, recipient, game
            )
            if counter is None:
                print(f"  [BOT/{bot_player.name}] Declines to counter further. Negotiation ends.")
                sleep()
                return False

            # Show bot's counter-counter to the human
            print(f"  [BOT/{bot_player.name}] Proposes a counter-counter-offer:")
            _print_offer(counter['offer_side'], counter['ask_side'], bot_player, recipient)

            print(f"  {recipient.name}, do you:")
            print("    [a] Accept    [c] Counter again    [r] Reject")
            while True:
                resp = input(f"  Your response [a/c/r]: ").strip().lower()
                if resp in ('a', 'c', 'r'):
                    break
                print("  Enter a, c, or r.")

            if resp == 'a':
                _execute_trade(bot_player, recipient, counter['offer_side'], counter['ask_side'], board, game)
                return True

            if resp == 'r':
                print(f"  {recipient.name} rejects. Negotiation ends.")
                divider()
                sleep()
                return False

            # Human wants to counter again — update reference state and loop
            current_bot_offer = counter['offer_side']
            current_bot_ask   = counter['ask_side']

        print("  Maximum counter rounds reached. Trade cancelled.")
        divider()
        sleep()
        return False


# ─────────────────────────────────────────────────
# MAIN ENTRY POINT  (human-initiated)
# ─────────────────────────────────────────────────

def _show_all_assets(players, board):
    """Print a full asset table for all players before trade selection."""
    divider('═')
    print("  PLAYER ASSETS OVERVIEW")
    divider('═')
    for p in players:
        bot_tag = f" [BOT/{p._bot.tier.upper()}]" if hasattr(p, '_bot') else ""
        print(f"\n  {p.name}{bot_tag}  —  Cash: ${p.cash}")
        tradeable = _owned_tradeable(p, board)
        if tradeable:
            for s in tradeable:
                colour = f" [{s.colour}]" if isinstance(s, Property) else " [Railroad]" if isinstance(s, Railroad) else " [Utility]"
                print(f"    • {s.name}{colour}  ${s.price}")
        else:
            print("    (no tradeable properties)")
        if p.comm_cards:
            print(f"    + {len(p.comm_cards)} Get Out of Jail Free card(s)")
    divider('═')
    sleep()


def initiate_trade(current_player, game):
    """Full human trade negotiation flow."""
    board   = game.board
    players = game.players

    others = [p for p in players if p.name != current_player.name]
    if not others:
        print("  No other players to trade with.")
        sleep()
        return

    # Show full asset overview before asking who to trade with
    _show_all_assets(others, board)

    print("  Who do you want to trade with?")
    for i, p in enumerate(others, 1):
        bot_tag = f" [BOT/{p._bot.tier.upper()}]" if hasattr(p, '_bot') else ""
        print(f"    {i}. {p.name}{bot_tag}  (cash: ${p.cash})")
    while True:
        raw = input("  Number (or 0 to cancel): ").strip()
        try:
            idx = int(raw)
            if idx == 0:
                print("  Trade cancelled.")
                sleep()
                return
            if 1 <= idx <= len(others):
                recipient = others[idx - 1]
                break
        except ValueError:
            pass
        print("  Invalid selection.")

    initiator = current_player
    round_num = 1
    last_offer = None
    last_ask = None

    while True:
        divider('═')
        label = "Initial offer" if round_num == 1 else "Counter-offer"
        print(f"  {label}  —  {initiator.name} → {recipient.name}")
        divider('═')
        sleep()

        # If initiator is a bot, use bot logic to build the offer
        if hasattr(initiator, '_bot'):
            print(f"  [BOT/{initiator.name}] Considers counter-offer...")
            sleep()
            
            counter = initiator._bot.generate_counter_offer(last_offer, last_ask, recipient, game)
            if counter:
                offer_side = counter['offer_side']
                ask_side = counter['ask_side']
                print(f"  [BOT/{initiator.name}] Proposes a counter-offer!")
                sleep()
            else:
                print(f"  [BOT/{initiator.name}] Declines to counter. Negotiation ends.")
                sleep()
                return
        else:
            # ── Step 1: What does the initiator WANT from the recipient? ──
            ask_side = _build_ask_side(initiator, recipient, board)

            ok, reason = _validate_side(ask_side, recipient, board)
            if not ok:
                print(f"  Invalid request: {reason}")
                sleep()
                continue

            # If nothing was asked for, abort
            if ask_side['cash'] == 0 and not ask_side['properties'] and ask_side['jail_cards'] == 0:
                print("  You didn't ask for anything. Trade cancelled.")
                sleep()
                return

            # ── Step 2: What does the initiator OFFER in return? ──
            offer_side = _build_offer_side(initiator, board, ask_side, recipient)

            ok, reason = _validate_side(offer_side, initiator, board)
            if not ok:
                print(f"  Invalid offer: {reason}")
                sleep()
                continue

        last_offer = offer_side
        last_ask = ask_side

        # Show full summary
        _print_offer(offer_side, ask_side, initiator, recipient)

        # ── Bot recipient: auto-evaluate ──
        if hasattr(recipient, '_bot'):
            accepted = recipient._bot.evaluate_incoming_trade(offer_side, ask_side, initiator, game)
            if accepted:
                print(f"  [BOT/{recipient.name}] Accepts the trade.")
                sleep()
                _execute_trade(initiator, recipient, offer_side, ask_side, board, game)
                return
            else:
                print(f"  [BOT/{recipient.name}] Rejects the trade.")
                sleep()
                # Swap roles to let bot consider a counter-offer next loop
                initiator, recipient = recipient, initiator
                round_num += 1
                continue

        # ── Human recipient: prompt ──
        print(f"  {recipient.name}, do you:")
        print("    [a] Accept")
        print("    [c] Counter-offer")
        print("    [r] Reject")
        while True:
            response = input(f"\n  {recipient.name}'s response [a/c/r]: ").strip().lower()
            if response in ('a', 'c', 'r'):
                break
            print("  Enter a, c, or r.")

        if response == 'a':
            _execute_trade(initiator, recipient, offer_side, ask_side, board, game)
            return

        if response == 'r':
            print(f"\n  {recipient.name} rejects. Trade cancelled.")
            divider()
            sleep()
            return

        # Counter-offer: swap roles
        print(f"\n  {recipient.name} is making a counter-offer...")
        sleep()
        initiator, recipient = recipient, initiator
        round_num += 1

        if round_num > 10:
            print("  Maximum rounds reached. Trade cancelled.")
            divider()
            sleep()
            return


