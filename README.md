# 🎩 Monopoly — Python Terminal Edition

## About this Project

This project was developed using an AI-assisted workflow with Claude.

I designed the project architecture, wrote the functional specification, defined the game mechanics, broke the implementation into modules, tested the game extensively, identified bugs, and iteratively refined the design through detailed prompts.

Claude generated and refactored most of the implementation based on those specifications and feedback.

The project serves as an exploration of AI-assisted software engineering, prompt engineering, iterative testing, and system design.

It is a fully-featured, terminal-based Monopoly implementation in Python. Supports 1–8 players in any mix of humans and bots, with a complete rule-set, a multi-round trade negotiation engine, and three distinct bot AI tiers each with their own strategy.

---

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [How to Play](#how-to-play)
  - [Command Reference](#command-reference)
  - [Game Setup](#game-setup)
  - [Turns](#turns)
  - [Buying Properties](#buying-properties)
  - [Auctions](#auctions)
  - [Building Houses & Hotels](#building-houses--hotels)
  - [Mortgaging & Redeeming](#mortgaging--redeeming)
  - [Jail](#jail)
  - [Bankruptcy](#bankruptcy)
- [Trading System](#trading-system)
  - [Initiating a Trade](#initiating-a-trade)
  - [Counter-Offers](#counter-offers)
- [Bot AI](#bot-ai)
  - [EasyBot — The Impulse Buyer](#easybot--the-impulse-buyer)
  - [MediumBot — The Value Shopper](#mediumbot--the-value-shopper)
  - [HardBot — The Shark](#hardbot--the-shark)
  - [Bot Trade Guardrails](#bot-trade-guardrails)
- [Save & Load](#save--load)
- [Module Overview](#module-overview)

---

## Features

- **Full Monopoly board** — all 40 spaces, including properties, railroads, utilities, taxes, Community Chest, Chance, Go, Jail, Free Parking, and Go To Jail
- **2–8 players** in any mix of humans and bots
- **Three bot difficulty tiers** with distinct buying, building, auctioning, and trading strategies
- **Complete property management** — buy, build, sell, mortgage, and redeem
- **English-style auction** whenever any player declines a property purchase
- **Full trade negotiation** — multi-asset offers (cash + properties + Jail Free cards), bot-to-bot trades, bot-to-human trades, and a multi-round counter-offer loop for human recipients
- **Jail mechanics** — roll for doubles, pay the fine, or use a Get Out of Jail Free card
- **Automatic insolvency resolution** — houses sold off, then properties mortgaged before bankruptcy is declared
- **Bankruptcy handling** — assets transfer to the creditor (with mortgage interest) or return to the Bank
- **Doubles rules** — extra roll on doubles, sent to jail on three consecutive doubles
- **Chance & Community Chest** — full card decks including movement cards (advance to nearest railroad/utility with correct rent rules), repairs, birthday collections, and more
- **Save & Load** — persist any game state to disk and resume later
- **Game log export** — dump the full runtime log to a text file
- **Net worth standings** — live leaderboard including property valuations

---

## Project Structure

```
monopoly/
├── game.py          # Entry point — command loop, display, setup, turn routing
├── state.py         # GameState — turn management, space resolution, rent, bankruptcy
├── objects.py       # All board object classes (Property, Railroad, Utility, Player, Dice, cards…)
├── board.py         # BOARD list, colour groups, helper queries (nearest railroad, etc.)
├── bots.py          # EasyBot, MediumBot, HardBot — all AI logic
├── trades.py        # Trade flow — human UI, bot routing, counter-offer negotiation
├── persistence.py   # Save/load serialisation and log export
└── README.md
```

---

## Getting Started

**Requirements:** Python 3.8 or later — no third-party packages needed.

```bash
# Clone the repository
git clone https://github.com/<mikedami>/<monopoly-game>.git
cd <monopoly-game>

# Run the game
python game.py
```

At launch you'll be asked whether to start a new game or load a save, then guided through player and bot setup.

---

## How to Play

### Game Setup

1. Enter the number of human players (1–8).
2. Enter how many Easy, Medium, and Hard bots to add (total players must be 2–8).
3. Enter a name for each human player.

Bot names are randomly drawn from themed pools (`Rookie`, `Bumble`… for Easy; `Sterling`, `Marlowe`… for Medium; `Magnus`, `Cipher`, `Specter`… for Hard).

### Command Reference

| Command | Shortcut | When available | Description |
|---|---|---|---|
| `roll` | `r` | Pre-roll | Roll dice and move |
| `build` | `b` | Any time | Buy a house/hotel on a monopoly |
| `sell` | `s` | Any time | Sell a house/hotel for half its cost |
| `mortgage` | `m` | Any time | Mortgage an unimproved property |
| `redeem` | `u` | Any time | Unmortgage a property |
| `trade` | `t` | Any time | Propose a trade with another player |
| `status` | `st` | Any time | View your position, cash, and assets |
| `standings` | `sd` | Any time | View all players' net worth |
| `board` | `bd` | Any time | Full board overview (owners, buildings, rent) |
| `save` | `sv` | Any time | Save the current game to disk |
| `export` | `ex` | Any time | Export the game log to a text file |
| `jail pay` | `jp` | In jail, pre-roll | Pay $50 to leave jail |
| `jail card` | `jc` | In jail, pre-roll | Use a Get Out of Jail Free card |
| `end turn` | `e` | Post-roll | End your turn |
| `help` | `h` | Any time | Show the command menu |
| `quit` | `q` | Any time | Quit the game |

### Turns

Each turn follows this order:

1. **Pre-roll actions** — build, mortgage, trade, view status, etc.
2. **Roll** (`r`) — dice are rolled, the player moves, and the landed space is resolved automatically.
3. **Purchase decision** — if the space is unowned, you're prompted to buy or send it to auction.
4. **Post-roll actions** — build, sell, mortgage, trade, end turn.
5. **Doubles** — rolling doubles grants an extra roll. Three consecutive doubles sends you to jail.

### Buying Properties

When you land on an unowned property, railroad, or utility you're offered the chance to buy it at face value. If you decline (or can't afford it), the property goes to an **English auction** open to all players.

### Auctions

All players bid in rotation. The minimum bid increases by $1 above the current high bid after each accepted bid. Passing removes you from the round. If nobody bids, the property stays with the Bank.

Bots use strategic maximum bids:
- **EasyBot** bids up to the face value.
- **MediumBot** bids 20 % over face value for colours where it already owns one, and 10 % below for everything else.
- **HardBot** bids up to 60 % over face value to deny a near-monopoly opponent, and 30 % over to complete its own set.

### Building Houses & Hotels

You must own a complete colour group (monopoly) before building. Houses must be placed evenly across all properties in the group. The Bank has a limited supply of 32 houses and 12 hotels — if the bank runs out, no further construction is possible until houses are sold back.

Hotels replace 4 houses on a single property. Selling a hotel returns 4 houses to the bank.

### Mortgaging & Redeeming

Any unimproved property can be mortgaged for half its face value. While mortgaged, no rent is collected on it. To redeem, pay the mortgage value plus 10 % interest.

### Jail

A player is sent to jail by:
- Landing on the **Go To Jail** space
- Drawing a **Go to Jail** Chance or Community Chest card
- Rolling **three consecutive doubles**

In jail you can:
- **Roll for doubles** — released immediately on a double (no extra roll)
- **Pay the $50 fine** before rolling
- **Use a Get Out of Jail Free card**

After 3 turns without rolling doubles, you must pay the $50 fine and move.

### Bankruptcy

If you cannot pay a debt (rent, tax, or fine) even after selling all houses and mortgaging all properties, you are declared bankrupt:

- **Bankrupt to a player** — all your remaining cash and properties transfer to the creditor. Mortgaged properties incur a 10 % interest charge to the new owner.
- **Bankrupt to the Bank** — all your properties are unimproved, unmortgaged, and returned to the Bank for future auction.

---

## Trading System

### Initiating a Trade

Type `t` (or `trade`) on your turn to open a trade. You'll see a full asset overview of all other players, then:

1. **Choose a trade partner.**
2. **Build your ask** — specify how much cash, which properties, and how many Jail Free cards you want from them.
3. **Build your offer** — specify what cash, properties, and Jail Free cards you'll give in return.
4. **The offer is displayed** and sent to the recipient.

The recipient can **Accept**, **Counter**, or **Reject**.

Trades can include any mix of:
- Cash
- Unimproved properties (including mortgaged ones)
- Get Out of Jail Free cards

### Counter-Offers

When a bot proposes a trade to a human player, the human can now also **counter** rather than simply accept or reject. This opens a negotiation loop (up to 5 rounds) where:

1. **Human specifies a counter** — new ask and offer amounts.
2. **Bot evaluates the counter** using its tier-specific logic.
3. If the bot rejects, it may propose its own **counter-counter**.
4. The human can then accept, reject, or counter again.

When a human initiates a trade toward a bot, the same loop applies from the other direction — the bot rejects and proposes counters until both sides agree or negotiations collapse.

---

## Bot AI

Bots act automatically each turn: they decide whether to use a Jail card or pay, whether to buy or skip a property, how much to bid at auction, whether to build, and whether to propose or respond to a trade.

### EasyBot — The Impulse Buyer

**Personality:** Buys anything it can afford, builds randomly, and makes straightforward trade decisions.

- **Buying:** Purchases any property as long as it has the cash.
- **Building:** Randomly selects a monopoly property and builds if it has more than $200 left over.
- **Auctions:** Bids up to the face value.
- **Trading — offers:** Scans for any monopoly it's one property away from and offers the cheapest property it can spare (from any colour). It will only make the offer if it would accept the same deal itself.
- **Trading — evaluation:** Accepts any incoming trade where what it receives is worth at least 1.5× what it gives away (or 0.8× if the trade completes one of its own monopolies).
- **Counter-offer evaluation:** When its own proposal is countered, it accepts if the final outgoing value is at most 2× the incoming value — considerably more lenient than its standard threshold.

### MediumBot — The Value Shopper

**Personality:** Prioritises mid-tier colour groups (Oranges, Reds, Pinks, Light Blues), avoids holding too little cash, and mortgages strategically.

- **Buying:** Maintains a cash buffer above the highest opponent rent. Always buys priority colours; skips low-traffic groups (Brown, Dark Blue, Utilities) if an opponent already has a share.
- **Building:** Builds up to 3 houses on monopoly properties, always keeping $150 in reserve.
- **Mortgaging:** Mortgages utilities first, then railroads, then non-monopoly properties to stay liquid.
- **Redeeming:** Unmortgages properties once cash exceeds $600.
- **Auctions:** 20 % over face value for colours where it has a head start.
- **Trading — offers:** Proposes 1-for-1 property swaps on colours one step away from a monopoly, only if the two properties are within $80 of each other in face value. Will only propose if it would accept the deal itself.
- **Trading — evaluation:** Requires incoming ≥ outgoing when the trade completes its monopoly; otherwise requires 2× value.
- **Counter-offers:** Will sweeten its counter by offering up to 35 % of its cash reserves, then throw in low-tier properties (Brown, Light Blue, Pink, Orange — the first 20 board positions) to close any remaining gap when it wants to complete a monopoly.

### HardBot — The Shark

**Personality:** Plays phase-aware, manipulates house supply, runs extortion trades, and never gives away an opponent's monopoly.

- **Buying:** Zero-buffer purchase when completing a monopoly or blocking an opponent from one. Conservative otherwise.
- **Building:** Locks properties at 4 houses (deliberately avoids hotels) to drain the bank's house supply and starve opponents.
- **Liquidation:** Immediately mortgages dead singleton properties when cash is tight and a live monopoly needs expanding.
- **Auctions:** Bids aggressively (up to 60 % premium) to deny near-monopoly opponents, and 30 % premium to complete its own.
- **Trading — offers:** Proposes extortion swaps — offers a lower-value property from a low-priority colour with cash-over-top to acquire the specific piece it needs. Will only propose if it would accept the deal itself.
- **Trading — evaluation:** Refuses to give away a monopoly-completing piece unless desperately cash-poor (<$200), in which case it demands 3× value. For monopoly-completing incoming trades, accepts at equal value (1×). All other trades require 1.5×.
- **Counter-offers:** When chasing a high-tier monopoly (Yellow, Green, Dark Blue), will offer up to 45 % of cash reserves plus low-tier properties (Brown, Light Blue, Pink) as sweeteners. For other monopolies, offers up to 25 % cash. Non-monopoly counters simply demand more cash from the human.

### Bot Trade Guardrails

All three bots **self-evaluate every trade proposal before sending it**. The bot mentally asks: "If I were the recipient, would I accept this?" If the answer is no, the trade is not proposed. This prevents the bots from spamming worthless or trivially one-sided offers.

---

## Save & Load

At any point during a human turn, type `save` (`sv`) to write the current game state to disk. On the next launch, choose `[l]oad` to resume from where you left off.

Type `export` (`ex`) to dump the full chronological game log to a `.txt` file.

---

## Module Overview

| File | Responsibility |
|---|---|
| `game.py` | Entry point. Runs the human command loop, bot turn dispatcher, purchase/auction UI, property management UI, and game setup wizard. |
| `state.py` | `GameState` class. Manages turn order, dice rolling, movement, space resolution, rent collection, insolvency, bankruptcy, jail logic, monopoly detection, and win condition. |
| `objects.py` | All data classes: `Property`, `Railroad`, `Utility`, `Player`, `Dice`, `Go`, `Tax`, `Jail`, `GoToJail`, `FreeParking`, `CommunityChest`, `Chance`, `Bank`. |
| `board.py` | The `BOARD` list (all 40 spaces in order) and helper functions: `get_colour_group`, `check_monopoly`, `get_railroad_count`, `get_utility_count`, `nearest_railroad`, `nearest_utility`. |
| `bots.py` | `EasyBot`, `MediumBot`, `HardBot` (all extending `BaseBot`). Each implements `jail_decision`, `should_buy`, `auction_max_bid`, `post_roll_actions`, `evaluate_incoming_trade`, `generate_counter_offer`, and `_maybe_trade`. |
| `trades.py` | Human trade UI (`initiate_trade`), bot trade routing (`bot_propose_trade`), counter-offer negotiation loop, asset validation, and trade execution (`_execute_trade`). |
| `persistence.py` | Game serialisation/deserialisation and log export. |
