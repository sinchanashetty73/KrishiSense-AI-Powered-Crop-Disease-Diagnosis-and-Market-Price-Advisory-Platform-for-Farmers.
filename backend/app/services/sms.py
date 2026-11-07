"""SMS sending through Amazon SNS.

SMS_PROVIDER=log  -> only writes the message to the log (development, default)
SMS_PROVIDER=sns  -> real SMS through Amazon SNS. The ECS task role / EC2 role needs sns:Publish.

INDIA: sending commercial SMS needs DLT registration (TRAI). Register your entity, a sender id (header) and
message templates, then set SNS_SENDER_ID, SNS_ENTITY_ID and SNS_TEMPLATE_ID. The text must match an approved
template, so keep the wording in services/alert_dispatch.py (SMS_TEMPLATES) identical to what you register.
See docs/AWS_DEPLOYMENT.md, section "SMS alerts". Verify attribute names against the current AWS SNS docs.
"""
import logging
import re

from ..config import settings

log = logging.getLogger("krishisense.sms")


def to_e164(phone: str) -> str | None:
    """'9876543210' -> '+919876543210'. Returns None when the number looks invalid."""
    digits = re.sub(r"[^\d+]", "", phone or "")
    if digits.startswith("+"):
        return digits if 11 <= len(digits) <= 16 else None
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    return None


def send_sms(phone: str, text: str) -> bool:
    """Returns True when the message was handed to the provider (or logged in development)."""
    number = to_e164(phone)
    if number is None:
        log.warning("Not sending SMS: invalid phone number")
        return False
    if settings.sms_provider != "sns":
        log.info("SMS to %s: %s", number, text)
        return True
    try:
        import boto3

        attrs = {"AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"}}
        if settings.sns_sender_id:
            attrs["AWS.SNS.SMS.SenderID"] = {"DataType": "String", "StringValue": settings.sns_sender_id}
        if settings.sns_entity_id:
            attrs["AWS.MM.SMS.EntityId"] = {"DataType": "String", "StringValue": settings.sns_entity_id}
        if settings.sns_template_id:
            attrs["AWS.MM.SMS.TemplateId"] = {"DataType": "String", "StringValue": settings.sns_template_id}
        boto3.client("sns", region_name=settings.aws_region).publish(
            PhoneNumber=number, Message=text, MessageAttributes=attrs)
        return True
    except Exception as e:  # network, permission, sandbox or DLT errors must never crash the job
        log.error("SNS publish failed: %s", e)
        return False
