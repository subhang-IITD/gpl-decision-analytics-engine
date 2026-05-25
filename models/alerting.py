"""Alert delivery: email (SendGrid) + WhatsApp (Interakt/Gupshup), brief 2.5/5.2.

Both channels are key-driven. Without keys, alerts are persisted to the warehouse
and printed to the console so the monitoring loop is always demonstrable and the
admin dashboard can show them. This is the single delivery point used by the
competitive-monitoring engine and the pipeline-failure alerts (brief 5.3).
"""
from __future__ import annotations

from config import get_settings


def send_email(to: str, subject: str, body: str) -> dict:
    cfg = get_settings().alerting
    if not cfg.sendgrid_api_key:
        print(f"[ALERT/email->console] to={to} | {subject}\n{body}\n")
        return {"channel": "email", "delivered": False, "fallback": "console"}
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        msg = Mail(from_email=cfg.sendgrid_from, to_emails=to, subject=subject, plain_text_content=body)
        SendGridAPIClient(cfg.sendgrid_api_key).send(msg)
        return {"channel": "email", "delivered": True}
    except Exception as exc:
        print(f"[ALERT/email->console fallback: {exc}] to={to} | {subject}\n{body}\n")
        return {"channel": "email", "delivered": False, "error": str(exc)}


def send_whatsapp(to: str, body: str) -> dict:
    cfg = get_settings().alerting
    if not cfg.whatsapp_api_key:
        print(f"[ALERT/whatsapp->console] to={to}\n{body}\n")
        return {"channel": "whatsapp", "delivered": False, "fallback": "console"}
    try:
        import requests

        endpoints = {
            "interakt": "https://api.interakt.ai/v1/public/message/",
            "gupshup": "https://api.gupshup.io/wa/api/v1/msg",
        }
        url = endpoints.get(cfg.whatsapp_provider, endpoints["interakt"])
        requests.post(url, headers={"Authorization": f"Bearer {cfg.whatsapp_api_key}"},
                      json={"to": to, "message": body}, timeout=20)
        return {"channel": "whatsapp", "delivered": True}
    except Exception as exc:
        print(f"[ALERT/whatsapp->console fallback: {exc}] to={to}\n{body}\n")
        return {"channel": "whatsapp", "delivered": False, "error": str(exc)}


def deliver(message: str, subject: str = "GPL Engine Alert", whatsapp: bool = False) -> list[dict]:
    cfg = get_settings().alerting
    results = [send_email(cfg.admin_email, subject, message)]
    if whatsapp:
        results.append(send_whatsapp(cfg.admin_email, message))
    return results
