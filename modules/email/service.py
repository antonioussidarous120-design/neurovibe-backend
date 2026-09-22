"""
Transactional email service — powered by Resend.

All sends are best-effort (failures are logged, never raised).
Templates use inline CSS for email-client compatibility.
"""

import logging
import resend
from datetime import date
from core.config import settings

logger = logging.getLogger(__name__)

SENDER      = "onboarding@resend.dev"
BRAND_NAME  = "NeuroVibe"
SITE_URL    = "https://getneruovibe.com"
PRICING_URL = "https://getneruovibe.com/pricing"
SUPPORT_EMAIL = "support.neurovibe@gmail.com"

FEATURE_LABELS: dict[str, str] = {
    "script_analyzer":   "Script Analyzer",
    "script_generator":  "Script Generator",
    "video_analysis":    "Video Analysis",
    "content_calendar":  "Content Calendar",
    "marketing_plan":    "Marketing Plan",
    "ads":               "Ads Generation",
}

PLAN_LABELS: dict[str, str] = {
    "free":    "Free",
    "creator": "Creator",
    "pro":     "Pro",
}

UPGRADE_TO: dict[str, str] = {
    "free":    "Creator ($29/mo)",
    "creator": "Pro ($59/mo)",
}


# ─── Shared HTML shell ────────────────────────────────────────────────────────

def _html_shell(content: str) -> str:
    """Wrap content in the NeuroVibe branded email shell."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="dark">
  <!--[if mso]><noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript><![endif]-->
</head>
<body style="margin:0;padding:0;background-color:#080809;-webkit-text-size-adjust:100%;mso-line-height-rule:exactly;">

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:#080809;padding:48px 20px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0"
               style="max-width:560px;width:100%;">

          <!-- ── Logo ── -->
          <tr>
            <td style="padding-bottom:36px;text-align:center;">
              <span style="font-size:26px;font-weight:900;color:#F59E0B;
                           letter-spacing:-0.03em;font-family:-apple-system,BlinkMacSystemFont,
                           'Segoe UI',Helvetica,Arial,sans-serif;">
                ⚡ {BRAND_NAME}
              </span>
            </td>
          </tr>

          <!-- ── Card ── -->
          <tr>
            <td style="background-color:#0c0c0e;border:1px solid rgba(245,158,11,0.18);
                       border-radius:16px;padding:40px 44px;">
              {content}
            </td>
          </tr>

          <!-- ── Footer ── -->
          <tr>
            <td style="padding-top:28px;text-align:center;">
              <p style="margin:0 0 6px;font-size:12px;color:#3f3f46;
                        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
                © 2026 {BRAND_NAME} &nbsp;·&nbsp;
                <a href="{SITE_URL}" style="color:#3f3f46;text-decoration:underline;">{SITE_URL}</a>
              </p>
              <p style="margin:0;font-size:11px;color:#27272a;
                        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
                Questions? Email
                <a href="mailto:{SUPPORT_EMAIL}" style="color:#27272a;text-decoration:underline;">{SUPPORT_EMAIL}</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


# ─── Button helper ────────────────────────────────────────────────────────────

def _cta_button(text: str, url: str) -> str:
    return f"""
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px auto 0;">
      <tr>
        <td align="center" style="border-radius:10px;background-color:#F59E0B;">
          <a href="{url}"
             style="display:inline-block;padding:14px 32px;
                    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
                    font-size:14px;font-weight:800;color:#000000;text-decoration:none;
                    border-radius:10px;letter-spacing:0.01em;">
            {text}
          </a>
        </td>
      </tr>
    </table>"""


def _divider() -> str:
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0;"><tr><td style="height:1px;background:rgba(255,255,255,0.06);"></td></tr></table>'


# ─── welcome_email ────────────────────────────────────────────────────────────

def welcome_email(to_email: str, name: str) -> None:
    """Send the onboarding welcome email to a new user."""
    if not settings.RESEND_API_KEY:
        logger.warning("[email] RESEND_API_KEY not set — skipping welcome email")
        return

    resend.api_key = settings.RESEND_API_KEY

    display_name = name.split()[0] if name else "there"

    content = f"""
      <!-- Headline -->
      <h1 style="margin:0 0 8px;font-size:28px;font-weight:900;color:#f4f4f5;
                 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
                 letter-spacing:-0.02em;">
        You're in. ⚡
      </h1>
      <p style="margin:0 0 24px;font-size:15px;color:#a1a1aa;line-height:1.6;
                font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
        Hey {display_name} — welcome to {BRAND_NAME}. Your account is live.
      </p>

      {_divider()}

      <!-- What to do first -->
      <p style="margin:0 0 12px;font-size:13px;font-weight:700;color:#71717a;
                text-transform:uppercase;letter-spacing:0.08em;
                font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
        Start here
      </p>

      <!-- Step 1 -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:14px;">
        <tr>
          <td width="36" valign="top"
              style="font-size:18px;padding-top:2px;">🧠</td>
          <td style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
            <p style="margin:0 0 2px;font-size:14px;font-weight:700;color:#f4f4f5;">Analyze a script</p>
            <p style="margin:0;font-size:13px;color:#71717a;line-height:1.5;">
              Paste any script into the Analyzer. Get emotion scores, drop moments,
              and rewrites — all grounded in neuroscience.
            </p>
          </td>
        </tr>
      </table>

      <!-- Step 2 -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:14px;">
        <tr>
          <td width="36" valign="top"
              style="font-size:18px;padding-top:2px;">✍️</td>
          <td style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
            <p style="margin:0 0 2px;font-size:14px;font-weight:700;color:#f4f4f5;">Generate a script</p>
            <p style="margin:0;font-size:13px;color:#71717a;line-height:1.5;">
              Pick a platform and emotion. {BRAND_NAME} writes a neuroscience-engineered
              script and scores it on 7 viral triggers instantly.
            </p>
          </td>
        </tr>
      </table>

      <!-- Step 3 -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td width="36" valign="top"
              style="font-size:18px;padding-top:2px;">🎬</td>
          <td style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
            <p style="margin:0 0 2px;font-size:14px;font-weight:700;color:#f4f4f5;">Test your hooks</p>
            <p style="margin:0;font-size:13px;color:#71717a;line-height:1.5;">
              Drop two hooks into the Hook Tester. Get a winner with the exact
              neuroscience reason why — backed by Loewenstein and Kahneman.
            </p>
          </td>
        </tr>
      </table>

      {_cta_button("Open NeuroVibe →", SITE_URL)}
    """

    try:
        resend.Emails.send({
            "from": SENDER,
            "to": [to_email],
            "subject": f"Welcome to {BRAND_NAME} ⚡",
            "html": _html_shell(content),
        })
        logger.info(f"[email] welcome sent to {to_email}")
    except Exception as exc:
        logger.warning(f"[email] welcome send failed for {to_email}: {exc}")


# ─── limit_reached_email ──────────────────────────────────────────────────────

def limit_reached_email(to_email: str, plan: str, feature: str, reset_date: str) -> None:
    """Send a limit-reached notification email."""
    if not settings.RESEND_API_KEY:
        logger.warning("[email] RESEND_API_KEY not set — skipping limit email")
        return

    resend.api_key = settings.RESEND_API_KEY

    feature_label = FEATURE_LABELS.get(feature, feature.replace("_", " ").title())
    plan_label    = PLAN_LABELS.get(plan, plan.title())
    upgrade_label = UPGRADE_TO.get(plan, "Pro ($59/mo)")

    # Format reset date nicely: "October 1" or fallback to raw string
    reset_label = reset_date
    try:
        reset_label = date.fromisoformat(str(reset_date)[:10]).strftime("%B %-d")
    except Exception:
        pass

    limit_values = {
        "free":    {"script_analyzer": 5,  "script_generator": 2,  "video_analysis": 0},
        "creator": {"script_analyzer": 50, "script_generator": 20, "video_analysis": 5},
    }
    limit_num = limit_values.get(plan, {}).get(feature, 0)
    limit_phrase = f"all {limit_num}" if limit_num else "your"

    content = f"""
      <!-- Icon -->
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
        <tr>
          <td style="width:52px;height:52px;background:rgba(239,68,68,0.08);
                     border:1px solid rgba(239,68,68,0.2);border-radius:14px;
                     text-align:center;vertical-align:middle;font-size:24px;">
            📉
          </td>
        </tr>
      </table>

      <!-- Headline -->
      <h1 style="margin:0 0 8px;font-size:24px;font-weight:900;color:#f4f4f5;
                 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
                 letter-spacing:-0.02em;">
        You've used {limit_phrase} {feature_label} runs
      </h1>
      <p style="margin:0 0 24px;font-size:15px;color:#a1a1aa;line-height:1.6;
                font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
        Your {plan_label} plan includes {limit_num} {feature_label} runs per month.
        You've hit that limit for this billing cycle.
      </p>

      {_divider()}

      <!-- Reset info -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="background:rgba(245,158,11,0.04);border:1px solid rgba(245,158,11,0.12);
                    border-radius:12px;padding:18px 20px;margin-bottom:24px;">
        <tr>
          <td style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
            <p style="margin:0 0 4px;font-size:12px;font-weight:700;color:#71717a;
                      text-transform:uppercase;letter-spacing:0.08em;">
              Your limit resets on
            </p>
            <p style="margin:0;font-size:20px;font-weight:900;color:#F59E0B;letter-spacing:-0.01em;">
              {reset_label}
            </p>
          </td>
        </tr>
      </table>

      <!-- Upgrade pitch -->
      <p style="margin:0 0 16px;font-size:14px;color:#a1a1aa;line-height:1.6;
                font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
        Want to keep going right now? Upgrade to <strong style="color:#f4f4f5;">{upgrade_label}</strong>
        for higher limits — or unlimited access on Pro.
      </p>

      <!-- Feature comparison teaser -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="margin-bottom:8px;">
        <tr>
          <td style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
                     font-size:13px;color:#71717a;padding:8px 0;
                     border-bottom:1px solid rgba(255,255,255,0.06);">
            {feature_label} — {plan_label}
          </td>
          <td align="right"
              style="font-family:'Courier New',Courier,monospace;font-size:13px;
                     color:#ef4444;font-weight:700;padding:8px 0;
                     border-bottom:1px solid rgba(255,255,255,0.06);">
            {limit_num} / mo
          </td>
        </tr>
        <tr>
          <td style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
                     font-size:13px;color:#f4f4f5;padding:8px 0;font-weight:600;">
            {feature_label} — {"Creator" if plan == "free" else "Pro"}
          </td>
          <td align="right"
              style="font-family:'Courier New',Courier,monospace;font-size:13px;
                     color:#10B981;font-weight:700;padding:8px 0;">
            {"50 / mo" if plan == "free" else "Unlimited"}
          </td>
        </tr>
      </table>

      {_cta_button("Upgrade my plan →", PRICING_URL)}

      <p style="margin:24px 0 0;font-size:12px;color:#52525b;text-align:center;
                font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
        Or wait until {reset_label} — your limit resets automatically, no action needed.
      </p>
    """

    try:
        resend.Emails.send({
            "from": SENDER,
            "to": [to_email],
            "subject": f"You've hit your {BRAND_NAME} {feature_label} limit for this month",
            "html": _html_shell(content),
        })
        logger.info(f"[email] limit_reached sent to {to_email} feature={feature} plan={plan}")
    except Exception as exc:
        logger.warning(f"[email] limit_reached send failed for {to_email}: {exc}")
