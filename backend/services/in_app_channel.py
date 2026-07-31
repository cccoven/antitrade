"""Built-in notification channel for the AntiTrade inbox."""

from services.notification_channels import ChannelMessage, SendResult


class InAppChannelAdapter:
    def send(self, channel, message: ChannelMessage) -> SendResult:
        return SendResult()
