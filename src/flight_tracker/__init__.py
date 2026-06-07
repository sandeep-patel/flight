"""Flight Tracker.

A small, cleanly-layered application that monitors Qantas flight prices
(reward points or cash) and sends a Telegram alert when an offer drops
below a configured target.

Layers (dependencies point inwards only):

- ``domain``         : framework-free entities and ports (interfaces).
- ``application``    : use cases orchestrating the domain.
- ``infrastructure`` : adapters (Playwright, Telegram, config, logging).
"""

__version__ = "0.1.0"
