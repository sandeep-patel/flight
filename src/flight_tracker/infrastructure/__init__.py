"""Infrastructure layer: adapters and configuration.

Implements the domain ports using concrete technologies (Playwright,
Telegram, environment variables). This is the only layer allowed to
import third-party SDKs and talk to the outside world.
"""
