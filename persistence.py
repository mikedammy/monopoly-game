"""
persistence.py — Save/Load state management and log export.
"""

import json
import os
import time
from board import BOARD
from objects import Property, Railroad, Utility

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves")
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)


def get_space_by_name(name):
    return next((s for s in BOARD if getattr(s, 'name', None) == name), None)


# ─────────────────────────────────────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────────────────────────────────────

def save_game(game, filename="monopoly_save.json"):
    path = os.path.join(SAVE_DIR, filename)

    player_data = []
    for p in game.players:
        player_data.append({
            'name':       p.name,
            'cash':       p.cash,
            'position':   p.position,
            'in_jail':    p.jailed,            # use .jailed (the real property)
            'jail_turns': p.jail_turns,
            'comm_cards': list(p.comm_cards),  # copy list
            'properties': list(p.properties),  # copy list
            'is_bot':     hasattr(p, '_bot'),
            'bot_tier':   p._bot.tier if hasattr(p, '_bot') else None,
        })

    board_data = []
    for space in BOARD:
        if not isinstance(space, (Property, Railroad, Utility)):
            continue
        entry = {
            'name':         space.name,
            'owner':        space.owner,       # already a string ('Bank' or player name)
            'is_mortgaged': space.is_mortgaged,
        }
        if isinstance(space, Property):
            entry['n_houses'] = space.n_houses    # int 0-5
        board_data.append(entry)

    snapshot = {
        'meta': {
            'timestamp':      time.time(),
            'round_number':   game.round_number,
            'turn_index':     game.turn_index,
            'doubles_streak': game.doubles_streak,
        },
        'players': player_data,
        'board':   board_data,
        'game_logs': game.logs,
    }

    try:
        with open(path, 'w') as f:
            json.dump(snapshot, f, indent=4)
        print(f"\n  [SAVE] Game saved to: {path}")
        return True
    except Exception as e:
        print(f"\n  [!] Save failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# LOAD
# ─────────────────────────────────────────────────────────────────────────────

def load_game(filename="monopoly_save.json"):
    path = os.path.join(SAVE_DIR, filename)
    if not os.path.exists(path):
        print(f"\n  [!] Save file not found: {path}")
        return None

    try:
        with open(path, 'r') as f:
            snap = json.load(f)

        from state import GameState
        from bots import EasyBot, MediumBot, HardBot
        from board import jail as board_jail

        names = [p['name'] for p in snap['players']]
        game = GameState(names)

        # Restore meta
        game.round_number   = snap['meta']['round_number']
        game.turn_index     = snap['meta']['turn_index']
        game.doubles_streak = snap['meta']['doubles_streak']
        game.logs           = snap['game_logs']

        # ── Restore players ───────────────────────────────────────────────
        for p_snap in snap['players']:
            p = game._get_player(p_snap['name'])
            p.cash = p_snap['cash']

            # Restore position via setter (wraps mod 40)
            p._Player__position = p_snap['position'] % 40

            # Restore jail state directly on private attrs to avoid setter
            # ValueError (setter raises if state matches current state)
            target_jail = p_snap['in_jail']
            if p.jailed != target_jail:
                if target_jail:
                    board_jail.add_prisoner(p)
                else:
                    # Only release if actually in jail dict
                    if p.name in board_jail._Jail__prisoners:
                        board_jail.release(p)

            p._Player__jail_turns = p_snap['jail_turns']

            # Restore comm_cards list directly
            p._Player__comm_cards = list(p_snap['comm_cards'])

            # Restore properties list directly (bypass append-only setter)
            p._Player__properties = list(p_snap['properties'])

            # Re-attach bot
            if p_snap['is_bot']:
                tier = p_snap['bot_tier']
                cls  = {'easy': EasyBot, 'medium': MediumBot, 'hard': HardBot}.get(tier)
                if cls:
                    p._bot = cls(p)

        # ── Restore board spaces ──────────────────────────────────────────
        for s_snap in snap['board']:
            space = get_space_by_name(s_snap['name'])
            if space is None:
                continue

            # Set owner by string directly — bypass Player-expecting setter
            if isinstance(space, Property):
                space._Property__owner = s_snap['owner']
                space._Property__is_mortgaged = s_snap['is_mortgaged']
                # Restore house/hotel count
                n = s_snap.get('n_houses', 0)
                if n == 5:
                    space._Property__hotel    = True
                    space._Property__n_houses = 0
                else:
                    space._Property__hotel    = False
                    space._Property__n_houses = n
                # Restore rent to correct tier
                if space._Property__hotel:
                    space._Property__rent = space.rent_list[5]
                elif n > 0:
                    space._Property__rent = space.rent_list[n]
                else:
                    # Check if monopolised
                    from board import check_monopoly, get_colour_group
                    owner_name = s_snap['owner']
                    if owner_name != 'Bank' and check_monopoly(space.colour, owner_name):
                        space._Property__is_monopolised = True
                        space._Property__rent = space.rent_list[0] * 2
                    else:
                        space._Property__is_monopolised = False
                        space._Property__rent = space.rent_list[0]

            elif isinstance(space, Railroad):
                space._Railroad__owner        = s_snap['owner']
                space._Railroad__is_mortgaged = s_snap['is_mortgaged']
                # Recalculate railroad rent from owner's count
                if s_snap['owner'] != 'Bank':
                    from board import get_railroad_count
                    count = get_railroad_count(s_snap['owner'])
                    if count in space.RENT_TABLE:
                        space._Railroad__rent = space.RENT_TABLE[count]

            elif isinstance(space, Utility):
                space._Utility__owner        = s_snap['owner']
                space._Utility__is_mortgaged = s_snap['is_mortgaged']

        print(f"\n  [LOAD] Game loaded from: {path}")
        return game

    except Exception as e:
        print(f"\n  [!] Load failed: {e}")
        import traceback
        traceback.print_exc()
        return None


# ─────────────────────────────────────────────────────────────────────────────
# LOG EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def dump_runtime_logs(game, log_filename=None):
    if log_filename is None:
        log_filename = f"match_log_{int(time.time())}.txt"
    path = os.path.join(SAVE_DIR, log_filename)

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("        MONOPOLY RUNTIME LOG\n")
            f.write(f"        {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

            f.write("--- PLAYERS ---\n")
            for p in game.players:
                ctrl = p._bot.tier.upper() if hasattr(p, '_bot') else "HUMAN"
                f.write(f"  {p.name:<15} [{ctrl}]\n")
            f.write("\n" + "─" * 60 + "\n\n")

            f.write("--- EVENT LOG ---\n")
            for entry in game.logs:
                f.write(f"  {entry}\n")

            f.write("\n" + "─" * 60 + "\n")
            f.write("--- FINAL STANDINGS ---\n")
            ranked = sorted(game.players, key=lambda p: p.cash, reverse=True)
            for i, p in enumerate(ranked, 1):
                f.write(f"  {i}. {p.name:<15} ${p.cash}\n")

        print(f"  [LOG] Exported to: {path}")
        return True
    except Exception as e:
        print(f"  [!] Log export failed: {e}")
        return False
