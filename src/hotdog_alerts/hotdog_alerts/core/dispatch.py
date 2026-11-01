"""Sending what is spooled: oldest first, each channel once, a failing channel retried later."""

from __future__ import annotations

from dataclasses import dataclass, field

from hotdog_alerts.core.spool import Spool


@dataclass
class Flush:
    """What one pass over the spool did."""

    sent: int = 0
    failed: dict = field(default_factory=dict)  # channel -> error
    left: int = 0


class Dispatcher:
    """Sends spooled alerts on Telegram chats and the webhook."""

    def __init__(self, spool: Spool, telegram=None, webhook=None, robot: str = ''):
        self.spool, self.telegram, self.webhook, self.robot = spool, telegram, webhook, robot

    def channels(self, chat_ids) -> list[str]:
        """Return the channels an alert goes to now."""
        out = []
        if self.telegram is not None:
            out += [f'telegram:{c}' for c in chat_ids if str(c).strip()]
        if self.webhook is not None:
            out.append('webhook')
        return out

    def send(self, channel: str, alert) -> tuple[bool, str]:
        """Send an alert on one channel."""
        if channel.startswith('telegram:') and self.telegram is not None:
            return self.telegram.send(channel.split(':', 1)[1], alert)
        if channel == 'webhook' and self.webhook is not None:
            return self.webhook.send(alert, self.robot)
        return True, 'channel removed'  # not configured any more: nothing to do

    def flush(self, limit: int = 20) -> Flush:
        """Send up to limit alerts; a channel that fails is not tried again in this pass."""
        result = Flush()
        files = self.spool.files()
        for path in files[:limit]:
            alert, entry = self.spool.load(path)
            if alert is None:
                continue
            for channel in list(entry['pending']):
                if channel in result.failed:
                    continue
                ok, error = self.send(channel, alert)
                if ok:
                    entry['pending'].remove(channel)
                    result.sent += 1
                else:
                    result.failed[channel] = error
                    entry['attempts'] += 1
                    entry['error'] = f'{channel}: {error}'
            self.spool.update(path, entry)
        result.left = len(self.spool.files())
        return result
