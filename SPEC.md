# TD Sequential counting rules (plain-English spec)

This document describes, in words, how to count the two TD Sequential phases
(Setup and Countdown) and the two price levels that go with them. It is detailed
enough to implement without seeing any other source, and an implementation that
follows it matches the reference output bar for bar on the shared test cases.

TD Sequential is a method published by Tom DeMark. This is an independent
description of one concrete, fully specified variant of it, not DeMark's text.

Not included: TD Combo, risk levels, and the "true high / true low"
variants of the support and resistance levels. Nothing here is trading advice.

## Input

- An ordered list of bars, oldest first, each with open, high, low, close and a
  timestamp. Only closed bars are used. If the last bar is still forming, drop it
  before counting.
- Bars are consecutive on the chosen timeframe. Gaps are not filled and are not
  special: the rules look at "previous bar", "4 bars earlier" and "2 bars earlier"
  in list order.
- Counting starts from the first bar of the list with empty history. Everything
  below is evaluated once per bar, in list order, and the bar's result depends
  only on that bar and the state left by earlier bars.
- Open prices and volume are never used.

## 1. Setup

Two independent counters run side by side: a buy setup and a sell setup.

For each bar, compare its close with the close of the bar 4 bars earlier
(the bar whose position is current minus 4).

- Buy setup: the bar qualifies if close is strictly lower than that close.
- Sell setup: the bar qualifies if close is strictly higher than that close.
- If the list has fewer than 4 earlier bars, the bar does not qualify.
- A bar with equal closes qualifies for neither counter.

Counter update for each side:

- If the bar qualifies, the counter becomes previous value plus 1.
- If it does not qualify, the counter becomes 0.
- No price flip is needed to start a count: a counter simply starts at 1 on the
  first qualifying bar after a reset.

What happens after 9 (this is the standard configuration; the optional
"continuation" mode is off):

- The counter is not capped and does not restart. If the run continues the next
  values are 10, 11, 12, and so on, until a bar fails to qualify and the counter
  drops to 0.
- A "setup 9" is the bar on which the counter equals exactly 9. It happens once
  per run. Values of 10 and above are not a new setup 9.
- (If continuation mode were on, the bar after 9 would restart at 1 instead of
  10. It is not part of this spec; implementations use the behaviour above.)

Because the two comparisons are opposite, at most one of the two counters is
non-zero on a bar.

The earliest possible setup 9 is the 13th bar of the list (4 bars of history,
then 9 qualifying bars).

## 2. Support and resistance levels

Levels are created by a completed setup 9 and are tracked until price breaks
them. Buy and sell levels are kept in two separate lists.

Creation, evaluated on every bar before anything else that uses levels:

- On a buy setup 9: add a resistance level at the highest high of the latest 9
  bars, including the current bar.
- On a sell setup 9: add a support level at the lowest low of the latest 9 bars,
  including the current bar.
- A level is not added if its price is not above zero, or if a still-active
  level in the same list already has exactly the same price.
- A new level becomes the "latest" level of its list, and any previous level
  stops being the latest one.
- Each list keeps at most 20 levels. When a 21st is added, the oldest is dropped.

Breaking, evaluated on every bar right after creation, for every active level:

- A resistance level is broken when the bar's close is above the price, or the
  bar's low is above the price (the whole bar sits above it).
- A support level is broken when the bar's close is below the price, or the
  bar's high is below the price (the whole bar sits below it).
- A broken level becomes inactive for good. A level touched without being broken
  (price pokes through and closes back) stays active; touches are counted by the
  reference but do not change any output described here, so they are not part of
  the contract.

Active level reported per bar:

- Resistance: the price of the latest resistance level if it is still active,
  otherwise null.
- Support: the price of the latest support level if it is still active,
  otherwise null.
- Only the latest level is reported. If the latest level has been broken, the
  value is null even when an older level in the list is still active.
- Before any setup 9 has completed, both are null.

## 3. Countdown

Two countdowns run side by side. The buy countdown belongs to buy setup 9 and
needs an active resistance level. The sell countdown belongs to sell setup 9 and
needs an active support level.

Each countdown holds a signed integer, starting at 0. Its absolute value is the
number of qualifying bars counted so far. A negative sign means "this bar did
not qualify, the count is paused at that value". Zero has no sign.

Qualifying bar:

- Buy countdown: the bar's close is lower than or equal to the low of the bar 2
  bars earlier.
- Sell countdown: the bar's close is higher than or equal to the high of the bar
  2 bars earlier.
- With fewer than 2 earlier bars, a bar does not qualify.
- Qualifying bars need not be consecutive. They are not required to be below the
  previous close or to follow any particular pattern; just this one comparison.

Per-bar update, for one countdown (own = its own setup, other = the opposite
setup). Check the cases in this order and stop at the first that applies:

1. Own setup 9 completes on this bar: the value becomes 1 if the bar qualifies,
   otherwise 0. This starts the countdown on the setup-9 bar itself, and also
   restarts any countdown that was already running.
2. Otherwise, if the opposite setup completes its 9 on this bar, or the level this
   countdown needs (resistance for buy, support for sell) is not active: the value
   becomes 14. This is the cancellation state.
3. Otherwise, if the previous value has absolute value 12 and the bar qualifies and
   the 13-versus-8 test fails (see below): the value becomes -12 and the bar is
   flagged as deferred.
4. Otherwise, if the bar qualifies: the value becomes the absolute value of the
   previous value plus 1.
5. Otherwise: the value becomes the negative of the absolute value of the previous
   value (zero stays zero).

13-versus-8 test (only used when the previous absolute value is 12):

- The close of the bar on which the countdown reached exactly 8 is remembered.
  (Only a transition to a positive 8 counts; the remembered close is overwritten
  each time a countdown reaches 8.)
- Buy countdown: the 13th qualifying bar is accepted only if its low is lower
  than or equal to that remembered close. If its low is higher, the bar is
  deferred.
- Sell countdown: accepted only if its high is higher than or equal to that
  remembered close. If its high is lower, the bar is deferred.
- A deferred bar leaves the value at -12 (rule 3). The following bars repeat the
  same test, so the countdown completes on the first later qualifying bar that
  passes the test. While waiting, non-qualifying bars also keep -12.

Completion and what the numbers mean:

- A value of exactly 13 means the countdown has just completed on this bar. It
  is the only way a 13 appears.
- The rules do not stop at 13. If the level is still active and no opposite 9
  occurs, the next qualifying bar produces 14, then 15, and so on, with negative
  values on non-qualifying bars. Treat any absolute value of 14 or more as "no
  countdown in progress": it is the cancellation state, or an already finished
  countdown, and it carries no further meaning.
- Cancellation (rule 2) therefore comes from two causes: the opposite setup 9, or
  loss of the needed level (it was broken, or no level was ever created). The
  value stays at 14 as long as the level is missing, which is why every bar of a
  fresh list shows 14 until a setup 9 and its level exist.
- A new own setup 9 (rule 1) always overrides a cancelled or finished state and
  restarts the countdown.

## 4. Output contract

One record per input bar, in input order:

| field | type | meaning |
|---|---|---|
| t | integer | the bar's timestamp, copied from the input |
| buySetup | integer | buy setup counter (0 or more; exactly 9 marks a setup 9) |
| sellSetup | integer | sell setup counter, same meaning |
| buyCountdown | integer | signed buy countdown value; 13 means just completed; 14 or more means no countdown in progress |
| sellCountdown | integer | signed sell countdown value, same meaning |
| resistance | number or null | price of the active latest resistance level |
| support | number or null | price of the active latest support level |
| buyDeferred | boolean | true on a bar where the buy countdown was held at -12 by the 13-versus-8 test |
| sellDeferred | boolean | same for the sell countdown |
| buyPerfected | boolean | true only on a buy setup 9 bar whose bar 8 or bar 9 low is strictly below both the bar 6 low and the bar 7 low (bars numbered 1 to 9 within the setup) |
| sellPerfected | boolean | true only on a sell setup 9 bar whose bar 8 or bar 9 high is strictly above both the bar 6 high and the bar 7 high |
| bullishFlip | boolean | true when the previous bar closed below the close 4 bars before it and this bar closes above the close 4 bars earlier (needs 5 earlier bars) |
| bearishFlip | boolean | the mirror: previous close above its 4-bars-earlier close, this close below its 4-bars-earlier close |

The four fields above are information only. They never change a setup, countdown or level value, and a setup does not need a flip to start.

Notes for implementers:

- Prices are compared as plain floating-point numbers with no rounding.
- A bar where the countdown is cancelled or restarted is reported with that
  bar's own result; there is no look-ahead and results never change when later
  bars arrive.
- Counting from a different starting bar can change early results (a run that
  began before the first bar is invisible). Compare implementations only on the
  same bar list, started from the same first bar.
