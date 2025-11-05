"""
Alert notification service.
Sends alerts via SMS, Email, and Webhook.
"""
import logging
from typing import List
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

from shared.config import ControlPlaneConfig
from shared.models.alerts import Alert, NotificationChannel, DeliveryResult

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Multi-channel notification service.
    Supports SMS (Twilio), Email (SMTP), and Webhook.
    """

    def __init__(self, config: ControlPlaneConfig):
        self.config = config
        self._init_twilio()

    def _init_twilio(self):
        """Initialize Twilio client."""
        if self.config.TWILIO_ACCOUNT_SID and self.config.TWILIO_AUTH_TOKEN:
            try:
                from twilio.rest import Client
                self.twilio_client = Client(
                    self.config.TWILIO_ACCOUNT_SID,
                    self.config.TWILIO_AUTH_TOKEN,
                )
                logger.info("Twilio client initialized")
            except ImportError:
                logger.warning("Twilio library not installed. SMS notifications disabled.")
                self.twilio_client = None
            except Exception as e:
                logger.error(f"Failed to initialize Twilio: {e}")
                self.twilio_client = None
        else:
            logger.info("Twilio credentials not configured. SMS notifications disabled.")
            self.twilio_client = None

    def send_alert(self, alert: Alert, channels: List[NotificationChannel], recipients: List[str]) -> List[DeliveryResult]:
        """
        Send alert via specified channels.
        Returns list of delivery results.
        """
        results = []

        for channel in channels:
            if channel == NotificationChannel.SMS:
                for recipient in recipients:
                    if self._is_phone_number(recipient):
                        result = self._send_sms(alert, recipient)
                        results.append(result)

            elif channel == NotificationChannel.EMAIL:
                for recipient in recipients:
                    if self._is_email(recipient):
                        result = self._send_email(alert, recipient)
                        results.append(result)

            elif channel == NotificationChannel.WEBHOOK:
                for recipient in recipients:
                    if self._is_url(recipient):
                        result = self._send_webhook(alert, recipient)
                        results.append(result)

        return results

    def _send_sms(self, alert: Alert, phone_number: str) -> DeliveryResult:
        """Send SMS via Twilio."""
        if not self.twilio_client:
            return DeliveryResult(
                channel=NotificationChannel.SMS,
                recipient=phone_number,
                success=False,
                error_message="Twilio not configured",
            )

        try:
            # Format message
            message_body = f"DealerEye Alert: {alert.title}\n\n{alert.message}"
            if alert.clip_url:
                message_body += f"\n\nClip: {alert.clip_url}"

            # Send SMS
            message = self.twilio_client.messages.create(
                to=phone_number,
                from_=self.config.TWILIO_FROM_NUMBER,
                body=message_body,
            )

            logger.info(f"SMS sent to {phone_number}, SID: {message.sid}")
            return DeliveryResult(
                channel=NotificationChannel.SMS,
                recipient=phone_number,
                success=True,
            )

        except Exception as e:
            logger.error(f"Failed to send SMS to {phone_number}: {e}")
            return DeliveryResult(
                channel=NotificationChannel.SMS,
                recipient=phone_number,
                success=False,
                error_message=str(e),
            )

    def _send_email(self, alert: Alert, email_address: str) -> DeliveryResult:
        """Send email via SMTP."""
        if not self.config.SMTP_HOST:
            return DeliveryResult(
                channel=NotificationChannel.EMAIL,
                recipient=email_address,
                success=False,
                error_message="SMTP not configured",
            )

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"DealerEye Alert: {alert.title}"
            msg["From"] = self.config.SMTP_FROM_EMAIL
            msg["To"] = email_address

            # Plain text body
            text_body = f"""
DealerEye Alert

{alert.title}

{alert.message}

Severity: {alert.severity.value}
Time: {alert.triggered_at.isoformat()}

Site ID: {alert.site_id}
"""
            if alert.clip_url:
                text_body += f"\nClip: {alert.clip_url}"
            if alert.keyframe_url:
                text_body += f"\nKeyframe: {alert.keyframe_url}"

            # HTML body
            html_body = f"""
<html>
<body>
<h2>DealerEye Alert</h2>
<h3>{alert.title}</h3>
<p>{alert.message}</p>
<p><strong>Severity:</strong> {alert.severity.value.upper()}</p>
<p><strong>Time:</strong> {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
"""
            if alert.clip_url:
                html_body += f'<p><a href="{alert.clip_url}">View Clip</a></p>'
            if alert.keyframe_url:
                html_body += f'<p><img src="{alert.keyframe_url}" style="max-width: 600px;"></p>'
            html_body += """
</body>
</html>
"""

            part1 = MIMEText(text_body, "plain")
            part2 = MIMEText(html_body, "html")
            msg.attach(part1)
            msg.attach(part2)

            # Send email
            with smtplib.SMTP(self.config.SMTP_HOST, self.config.SMTP_PORT) as server:
                if self.config.SMTP_USERNAME and self.config.SMTP_PASSWORD:
                    server.starttls()
                    server.login(self.config.SMTP_USERNAME, self.config.SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"Email sent to {email_address}")
            return DeliveryResult(
                channel=NotificationChannel.EMAIL,
                recipient=email_address,
                success=True,
            )

        except Exception as e:
            logger.error(f"Failed to send email to {email_address}: {e}")
            return DeliveryResult(
                channel=NotificationChannel.EMAIL,
                recipient=email_address,
                success=False,
                error_message=str(e),
            )

    def _send_webhook(self, alert: Alert, webhook_url: str) -> DeliveryResult:
        """Send webhook notification."""
        try:
            import requests

            payload = {
                "alert_id": str(alert.alert_id),
                "title": alert.title,
                "message": alert.message,
                "severity": alert.severity.value,
                "alert_type": alert.alert_type.value,
                "site_id": str(alert.site_id),
                "triggered_at": alert.triggered_at.isoformat(),
                "clip_url": alert.clip_url,
                "keyframe_url": alert.keyframe_url,
                "context": alert.context,
            }

            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                logger.info(f"Webhook sent to {webhook_url}")
                return DeliveryResult(
                    channel=NotificationChannel.WEBHOOK,
                    recipient=webhook_url,
                    success=True,
                )
            else:
                logger.warning(f"Webhook returned {response.status_code}")
                return DeliveryResult(
                    channel=NotificationChannel.WEBHOOK,
                    recipient=webhook_url,
                    success=False,
                    error_message=f"HTTP {response.status_code}",
                )

        except Exception as e:
            logger.error(f"Failed to send webhook to {webhook_url}: {e}")
            return DeliveryResult(
                channel=NotificationChannel.WEBHOOK,
                recipient=webhook_url,
                success=False,
                error_message=str(e),
            )

    @staticmethod
    def _is_phone_number(s: str) -> bool:
        """Check if string is a phone number."""
        return s.startswith("+") or s.replace("-", "").replace(" ", "").isdigit()

    @staticmethod
    def _is_email(s: str) -> bool:
        """Check if string is an email."""
        return "@" in s and "." in s

    @staticmethod
    def _is_url(s: str) -> bool:
        """Check if string is a URL."""
        return s.startswith("http://") or s.startswith("https://")
