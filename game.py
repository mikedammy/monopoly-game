"""
game.py — Command loop and runtime engine.
All movement and space resolution goes through game.take_turn() in state.py.
"""

import time
from state import GameState
from objects import Property, Railroad, Utility
from board import BOARD
from trades import initiate_trade
from bots import EasyBot, MediumBot, HardBot, BOT_NAMES


# ─────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────

SLEEP = 1.0

COMMANDS = {
    'roll': 'r', 'build': 'b', 'sell': 's',
    'mortgage': 'm', 'redeem': 'u', 'trade': 't',
    'status': 'st', 'standings': 'sd', 'board': 'bd',
    'end turn': 'e', 'help': 'h', 'quit': 'q',
    'save': 'sv', 'export': 'ex',
    'jail pay': 'jp', 'jail card': 'jc',
}
SHORT_TO_LONG = {v: k for k, v in COMMANDS.items()}


# ─────────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────────

def sleep():
    time.sleep(SLEEP)


def divider(char='─', width=60):
    print(char * width)


def slow_print(msg):
    print(msg)
    sleep()


def normalise(raw):
    cleaned = raw.strip().lower()
    return SHORT_TO_LONG.get(cleaned, cleaned)


def prompt(msg, yes_no=False):
    while True:
        raw = input(f"\n  {msg} ").strip()
        if yes_no:
            if not raw or raw.lower() in ('y', 'yes'):
                return 'yes'
            if raw.lower() in ('n', 'no'):
                return 'no'
            print("  Please enter y or n.")
            continue
        return normalise(raw)


def show_options(rolled, jailed):
    if jailed:
        print("  roll[r]  jail pay[jp]  jail card[jc]  status[st]  help[h]")
    elif not rolled:
        print("  roll[r]  build[b]  sell[s]  mortgage[m]  redeem[u]  trade[t]  status[st]  standings[sd]  board[bd]  save[sv]  help[h]  quit[q]")
    else:
        print("  build[b]  sell[s]  mortgage[m]  redeem[u]  trade[t]  status[st]  standings[sd]  board[bd]  end turn[e]  save[sv]  help[h]  quit[q]")


def print_help():
    divider()
    print("""
  COMMANDS:
    roll (r)        — Roll dice and move
    build (b)       — Buy houses on a monopoly
    sell (s)        — Sell a house/hotel for cash
    mortgage (m)    — Mortgage a property for cash
    redeem (u)      — Unmortgage a property
    trade (t)       — Propose a trade with another player
    status (st)     — View your position and assets
    standings (sd)  — View all players' net worth
    end turn (e)    — End turn after rolling
    board (bd)      — Show full board status (owners, buildings, rent)
    save (sv)       — Save the current game
    export (ex)     — Export game log to text file
    jail pay (jp)   — Pay $50 to leave jail
    jail card (jc)  — Use Get Out of Jail Free card
    help (h)        — Show this menu
    quit (q)        — Quit the game
    """)
    divider()
    sleep()


def _owned_properties(player):
    return [s for s in BOARD if getattr(s, 'owner', None) == player.name]


def display_status(player):
    divider('═')
    print(f"  PLAYER: {player.name.upper()}")
    print(f"    Cash     : ${player.cash}")
    space = BOARD[player.position]
    print(f"    Position : [{player.position:02d}] {getattr(space, 'name', '?')}")
    print(f"    Jailed   : {player.jailed}")
    if player.jailed:
        print(f"    Jail turn: {player.jail_turns}")
    owned = _owned_properties(player)
    if owned:
        print("    Assets   :")
        for s in owned:
            m_tag = " [MORTGAGED]" if s.is_mortgaged else ""
            if isinstance(s, Property):
                h_tag = f" ({s.n_houses_str})" if s.n_houses > 0 else ""
            else:
                h_tag = ""
            print(f"      - {s.name}{h_tag}{m_tag}")
    else:
        print("    Assets   : None")
    if player.comm_cards:
        print(f"    Jail cards: {len(player.comm_cards)}")
    divider('─')
    sleep()


def board_status(game):
    """
    Print a full board overview grouped by colour group.
    Shows owner, house/hotel count, mortgage status, and current rent.
    """
    from board import COLOUR_ORDER, COLOUR_GROUPS
    from objects import Railroad, Utility, Property

    divider('═')
    print("  BOARD STATUS")
    divider('═')

    # ── Colour groups ────────────────────────────────────────
    for colour in COLOUR_ORDER:
        props = COLOUR_GROUPS.get(colour, [])
        print(f"\n  [{colour.upper()}]")
        for p in props:
            if p.is_mortgaged:
                status = "MORTGAGED"
            elif p.owner == 'Bank':
                status = "unowned"
            else:
                h = p.n_houses_str
                status = f"{p.owner}  {h}  rent=${p.rent}"
            print(f"    {p.name:<28} {status}")

    # ── Railroads ────────────────────────────────────────────
    print(f"\n  [RAILROADS]")
    for space in BOARD:
        if not isinstance(space, Railroad):
            continue
        if space.is_mortgaged:
            status = "MORTGAGED"
        elif space.owner == 'Bank':
            status = "unowned"
        else:
            status = f"{space.owner}  rent=${space.rent}"
        print(f"    {space.name:<28} {status}")

    # ── Utilities ────────────────────────────────────────────
    print(f"\n  [UTILITIES]")
    for space in BOARD:
        if not isinstance(space, Utility):
            continue
        if space.is_mortgaged:
            status = "MORTGAGED"
        elif space.owner == 'Bank':
            status = "unowned"
        else:
            status = f"{space.owner}  mult={space.rent_mult}×dice"
        print(f"    {space.name:<28} {status}")

    divider('═')
    sleep()


# ─────────────────────────────────────────────────
# PROPERTY MANAGEMENT (HUMAN)
# ─────────────────────────────────────────────────

def handle_build(player, game):
    from board import check_monopoly, get_colour_group
    owned = _owned_properties(player)
    props = [s for s in owned if isinstance(s, Property) and check_monopoly(s.colour, player.name) and not s.is_mortgaged]
    if not props:
        slow_print("  [!] No eligible monopoly properties to build on.")
        return

    print("\n  Select a property to build on:")
    for i, p in enumerate(props, 1):
        print(f"    {i}. {p.name:<28} Houses: {p.n_houses_str:<8} Cost: ${p.house_cost}")

    raw = input(f"  Choice (1–{len(props)}, Enter to cancel): ").strip()
    if not raw:
        return
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(props):
            target = props[idx]
            if player.cash < target.house_cost:
                slow_print(f"  [!] Can't afford ${target.house_cost}. Cash: ${player.cash}")
                return
                
            group = get_colour_group(target.colour)
            success, msg = target.build_house(group)
            
            if success:
                player.cash -= target.house_cost
                slow_print(f"  {msg}")
                slow_print(f"  Cash updated to ${player.cash}")
            else:
                slow_print(f"  [!] {msg}")
        else:
            slow_print("  [!] Invalid choice.")
    except ValueError:
        slow_print("  [!] Invalid input.")


def handle_sell(player):
    from board import get_colour_group
    owned = _owned_properties(player)
    props = [s for s in owned if isinstance(s, Property) and s.n_houses > 0]
    if not props:
        slow_print("  [!] No houses or hotels to sell.")
        return

    print("\n  Select a property to sell improvements from:")
    for i, p in enumerate(props, 1):
        print(f"    {i}. {p.name:<28} ({p.n_houses_str}) → Recover ${p.house_cost // 2}")

    raw = input(f"  Choice (1–{len(props)}, Enter to cancel): ").strip()
    if not raw:
        return
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(props):
            target = props[idx]
            group = get_colour_group(target.colour)
            success, sell_val, msg = target.sell_house(group)
            
            if success:
                player.cash += sell_val
                slow_print(f"  {msg}")
                slow_print(f"  Cash updated to ${player.cash}")
            else:
                slow_print(f"  [!] {msg}")
        else:
            slow_print("  [!] Invalid choice.")
    except ValueError:
        slow_print("  [!] Invalid input.")


def handle_mortgage(player):
    owned = _owned_properties(player)
    valid = [
        s for s in owned
        if not s.is_mortgaged
        and (not isinstance(s, Property) or s.n_houses == 0)
    ]
    if not valid:
        slow_print("  [!] No eligible properties to mortgage (sell houses first).")
        return

    print("\n  Select a property to mortgage:")
    for i, s in enumerate(valid, 1):
        print(f"    {i}. {s.name:<28} +${s.mortgage_price}")

    raw = input(f"  Choice (1–{len(valid)}, Enter to cancel): ").strip()
    if not raw:
        return
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(valid):
            target = valid[idx]
            target.is_mortgaged = True
            player.cash += target.mortgage_price
            slow_print(f"  Mortgaged {target.name}. +${target.mortgage_price}. Cash: ${player.cash}")
        else:
            slow_print("  [!] Invalid choice.")
    except ValueError:
        slow_print("  [!] Invalid input.")


def handle_redeem(player):
    owned = _owned_properties(player)
    mortgaged = [s for s in owned if s.is_mortgaged]
    if not mortgaged:
        slow_print("  [!] No mortgaged properties to redeem.")
        return

    print("\n  Select a property to redeem:")
    for i, s in enumerate(mortgaged, 1):
        print(f"    {i}. {s.name:<28} -${s.redeem_price}")

    raw = input(f"  Choice (1–{len(mortgaged)}, Enter to cancel): ").strip()
    if not raw:
        return
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(mortgaged):
            target = mortgaged[idx]
            if player.cash < target.redeem_price:
                slow_print(f"  [!] Can't afford ${target.redeem_price}. Cash: ${player.cash}")
                return
            target.is_mortgaged = False
            player.cash -= target.redeem_price
            slow_print(f"  Redeemed {target.name}. -${target.redeem_price}. Cash: ${player.cash}")
        else:
            slow_print("  [!] Invalid choice.")
    except ValueError:
        slow_print("  [!] Invalid input.")


# ─────────────────────────────────────────────────
# PURCHASE DECISION + AUCTION
# ─────────────────────────────────────────────────

def handle_purchase_decision(game, result):
    """Called when take_turn() returns action='purchase_decision'."""
    player = game.current_player
    space_name = result['space']
    price = result['price']
    space = next(s for s in BOARD if getattr(s, 'name', None) == space_name)

    if hasattr(player, '_bot'):
        bought = player._bot.handle_purchase(space, game)
        if not bought:
            run_english_auction(game, space)
        return

    divider()
    print(f"\n  {space_name} is unowned  |  Price: ${price}  |  Cash: ${player.cash}")
    divider()
    sleep()

    choice = prompt("Buy? [y/Enter = yes, n = no]:", yes_no=True)
    if choice == 'yes':
        success = game.confirm_purchase(player, space)
        if not success:
            slow_print("  Insufficient funds — going to auction.")
            run_english_auction(game, space)
    else:
        slow_print(f"  {player.name} passes — going to auction.")
        run_english_auction(game, space)

    divider()
    sleep()



def run_english_auction(game, space):
    print(f"\n  {'═'*50}")
    print(f"  AUCTION: {space.name}  (face value ${space.price})")
    print(f"  {'═'*50}")
    sleep()

    active_bidders = list(game.players)
    highest_bid    = 0
    highest_bidder = None
    min_bid        = 1

    while len(active_bidders) > 1:
        for player in list(active_bidders):
            if len(active_bidders) == 1:
                break

            print(f"\n  High bid: ${highest_bid}" +
                  (f" ({highest_bidder.name})" if highest_bidder else " (none)"))

            if hasattr(player, '_bot'):
                max_b = player._bot.auction_max_bid(space, highest_bid, game)
                if max_b >= min_bid:
                    highest_bid    = min_bid
                    highest_bidder = player
                    min_bid        = round(highest_bid * 1.1, 0)
                    slow_print(f"  [BOT/{player.name}] Bids ${highest_bid}.")
                else:
                    slow_print(f"  [BOT/{player.name}] Passes.")
                    active_bidders.remove(player)
                    if len(active_bidders) == 1:
                        break
                continue

            print(f"  {player.name} — cash: ${player.cash}  |  Min: ${min_bid}")
            raw = input(f"  {player.name}'s bid (Enter/0 to pass): $").strip()
            try:
                bid = int(raw) if raw else 0
            except ValueError:
                bid = 0

            if bid < min_bid or bid > player.cash:
                if bid != 0:
                    slow_print(f"  Invalid — must be at least ${min_bid} and within cash.")
                slow_print(f"  {player.name} passes.")
                active_bidders.remove(player)
                if len(active_bidders) == 1:
                    break
                continue

            highest_bid    = bid
            highest_bidder = player
            min_bid        = round(highest_bid*1.1, 0)
            slow_print(f"  {player.name} bids ${bid}!")

        if len(active_bidders) == 1:
            break
        if not highest_bidder and len(active_bidders) == 0:
            break

    divider()
    if highest_bidder:
        slow_print(f"  {highest_bidder.name} wins {space.name} for ${highest_bid}!")
        game.complete_auction_purchase(highest_bidder, space, highest_bid)
    else:
        slow_print(f"  No bids — {space.name} stays with the Bank.")
    divider()
    sleep()


# ─────────────────────────────────────────────────
# POST-ROLL / PRE-ROLL ACTION DISPATCH
# ─────────────────────────────────────────────────

def handle_action(game, command):
    """Handles any non-roll command regardless of pre/post roll."""
    player = game.current_player

    if command in ('build', 'b'):
        handle_build(player, game)
    elif command in ('sell', 's'):
        handle_sell(player)
    elif command in ('mortgage', 'm'):
        handle_mortgage(player)
    elif command in ('redeem', 'u'):
        handle_redeem(player)
    elif command in ('trade', 't'):
        initiate_trade(player, game)
    elif command in ('status', 'st'):
        display_status(player)
    elif command in ('standings', 'sd'):
        game.standings()
        sleep()
    elif command in ('board', 'bd'):
        board_status(game)
    elif command in ('save', 'sv'):
        from persistence import save_game
        save_game(game)
    elif command in ('export', 'ex'):
        from persistence import dump_runtime_logs
        dump_runtime_logs(game)
    elif command in ('help', 'h'):
        print_help()
    else:
        slow_print("  [!] Unknown command. Type 'h' for help.")


# ─────────────────────────────────────────────────
# BOT TURN
# ─────────────────────────────────────────────────

def run_bot_turn(game):
    player = game.current_player
    bot    = player._bot

    time.sleep(1.8)   # pause between bot turns so output is readable
    divider('═')
    slow_print(f"  [BOT/{bot.tier.upper()}] {player.name}'s turn  |  Round {game.round_number}  |  Cash: ${player.cash}")
    divider('═')
    time.sleep(1.0)

    # Pre-roll jail decision
    if player.jailed:
        bot._handle_jail(game)
        if player.jailed and bot.jail_decision(game) == 'roll':
            pass  # fall through to take_turn which calls _take_jail_turn

    result = game.take_turn()
    divider()
    time.sleep(1.0)

    bot.take_bot_turn(game, result)


# ─────────────────────────────────────────────────
# HUMAN TURN
# ─────────────────────────────────────────────────

def run_turn(game):
    player = game.current_player

    divider('═')
    print(f"  {player.name}'s turn  |  Round {game.round_number}  |  Cash: ${player.cash}")
    divider('═')
    sleep()

    rolled = False

    while True:
        show_options(rolled=rolled, jailed=player.jailed)
        command = prompt(f"{player.name} >>")

        # ── Quit ────────────────────────────────────────────────
        if command in ('quit', 'q'):
            if prompt("Quit? All progress lost. [y/n]:", yes_no=True) == 'yes':
                return 'quit'
            continue

        # ── End turn ────────────────────────────────────────────
        if command in ('end turn', 'e'):
            if not rolled:
                slow_print("  [!] You must roll first.")
                continue
            divider()
            slow_print(f"  {player.name} ends their turn.")
            game.next_turn()
            return 'ok'

        # ── Roll ────────────────────────────────────────────────
        if command in ('roll', 'r'):
            if rolled:
                slow_print("  [!] Already rolled. Use 'e' to end turn.")
                continue

            result = game.take_turn()
            divider()
            sleep()

            # Purchase decision
            if result.get('action') == 'purchase_decision':
                handle_purchase_decision(game, result)
                if result.get('extra_roll') and not player.jailed:
                    slow_print(f"\n  {player.name} rolled doubles — bonus roll!")
                    _run_bonus_roll(game, player)
                    return 'ok'
                else:
                    rolled = True
                    continue

            # Sent to jail / stayed in jail — turn ends
            if result.get('action') in ('go_to_jail', 'in_jail'):
                divider()
                slow_print(f"  {player.name}'s turn ends.")
                game.next_turn()
                return 'ok'

            # Doubles — bonus roll
            if result.get('extra_roll') and not player.jailed:
                slow_print(f"\n  {player.name} rolled doubles — bonus roll!")
                _run_bonus_roll(game, player)
                return 'ok'

            rolled = True
            continue

        # ── Jail shortcuts (pre-roll only) ───────────────────────
        if command in ('jail pay', 'jp'):
            if not player.jailed:
                slow_print("  [!] You are not in jail.")
                continue
            game.pay_jail_fine(player)
            sleep()
            continue

        if command in ('jail card', 'jc'):
            if not player.jailed:
                slow_print("  [!] You are not in jail.")
                continue
            game.use_jail_card(player)
            sleep()
            continue

        # ── Everything else ─────────────────────────────────────
        handle_action(game, command)


def _run_bonus_roll(game, player):
    """Extra roll loop after doubles."""
    while True:
        divider()
        print(f"  {player.name}'s bonus roll  |  Cash: ${player.cash}")
        divider()
        sleep()
        show_options(rolled=False, jailed=player.jailed)
        command = prompt(f"{player.name} >>")

        if command in ('roll', 'r'):
            result = game.take_turn()
            divider()
            sleep()

            if result.get('action') == 'purchase_decision':
                handle_purchase_decision(game, result)
                if result.get('extra_roll') and not player.jailed:
                    slow_print(f"\n  {player.name} rolled doubles again!")
                    continue
                else:
                    _post_roll_loop(game, player)
                    return

            if result.get('action') in ('go_to_jail',):
                return

            if result.get('extra_roll') and not player.jailed:
                slow_print(f"\n  {player.name} rolled doubles again!")
                continue

            _post_roll_loop(game, player)
            return

        elif command in ('jail pay', 'jp'):
            game.pay_jail_fine(player)
            sleep()
        elif command in ('jail card', 'jc'):
            game.use_jail_card(player)
            sleep()
        else:
            handle_action(game, command)


def _post_roll_loop(game, player):
    """Actions after final roll of turn, until 'end turn'."""
    while True:
        show_options(rolled=True, jailed=False)
        command = prompt(f"{player.name} >>")

        if command in ('end turn', 'e'):
            divider()
            slow_print(f"  {player.name} ends their turn.")
            game.next_turn()
            return

        if command in ('quit', 'q'):
            if prompt("Quit? [y/n]:", yes_no=True) == 'yes':
                raise SystemExit(0)
            continue

        handle_action(game, command)


# ─────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────

_used_bot_names = set()

def _pick_bot_name(tier):
    available = [n for n in BOT_NAMES[tier] if n not in _used_bot_names]
    import random
    name = random.choice(available) if available else f"{tier.capitalize()}{len(_used_bot_names)+1}"
    _used_bot_names.add(name)
    return name


def setup_game():
    print("\n" + "═" * 55)
    print("            MONOPOLY")
    print("═" * 55)
    time.sleep(0.5)

    # Human count
    while True:
        try:
            n_humans = int(input("\n  How many human players? (1–8): "))
            if 1 <= n_humans <= 8:
                break
            print("  Must be 1–8.")
        except ValueError:
            print("  Enter a number.")

    # Bot counts
    max_bots = 8 - n_humans
    bot_assignments = []  # [(name, cls)]

    if max_bots > 0:
        print(f"\n  How many bots? (0–{max_bots} total)")
        while True:
            try:
                easy_n = int(input("    Easy bots   : ").strip() or 0)
                med_n  = int(input("    Medium bots : ").strip() or 0)
                hard_n = int(input("    Hard bots   : ").strip() or 0)
                total_bots = easy_n + med_n + hard_n
                if total_bots > max_bots:
                    print(f"  [!] Too many bots ({total_bots}). Max is {max_bots}.")
                    continue
                if n_humans + total_bots < 2:
                    print("  [!] Need at least 2 players total.")
                    continue
                break
            except ValueError:
                print("  Enter numbers (blank = 0).")

        for _ in range(easy_n):
            bot_assignments.append((_pick_bot_name('easy'), EasyBot))
        for _ in range(med_n):
            bot_assignments.append((_pick_bot_name('medium'), MediumBot))
        for _ in range(hard_n):
            bot_assignments.append((_pick_bot_name('hard'), HardBot))

    # Human names
    bot_name_set = {b[0] for b in bot_assignments}
    human_names  = []
    print()
    for i in range(n_humans):
        while True:
            name = input(f"  Player {i+1} name: ").strip()
            if not name:
                print("  Name can't be empty.")
            elif name in human_names or name in bot_name_set:
                print("  Name taken.")
            else:
                human_names.append(name)
                break

    all_names = human_names + [b[0] for b in bot_assignments]
    game = GameState(all_names)

    for bot_name, bot_cls in bot_assignments:
        p = game._get_player(bot_name)
        p._bot = bot_cls(p)
        slow_print(f"  Registered [{p._bot.tier.upper()}] bot: {bot_name}")

    return game


# ─────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────

def main():
    print("\n  Start a [n]ew game or [l]oad a save?")
    choice = input("  [n/l]: ").strip().lower()

    if choice == 'l':
        from persistence import load_game
        game = load_game()
        if game is None:
            slow_print("  No save found — starting new game.")
            game = setup_game()
    else:
        game = setup_game()

    slow_print("\n  Game started! Type 'h' for help.\n")

    while game.active and len(game.players) > 1:
        player = game.current_player
        try:
            if hasattr(player, '_bot'):
                run_bot_turn(game)
            else:
                outcome = run_turn(game)
                if outcome == 'quit':
                    break
        except SystemExit:
            break

    if game.players:
        winner = max(game.players, key=lambda p: p.net_worth(BOARD))
        print(f"\n  GAME OVER — {winner.name} wins with ${winner.cash}!")


if __name__ == "__main__":
    main()
