"""
Branded HTML email layout aligned with frontend (gradient hero, primary blue, card UI).
Uses tables + inline CSS for client compatibility (Gmail, Outlook, Apple Mail).
"""
from __future__ import annotations

import html
from typing import Optional
from urllib.parse import urlparse

from app.core.config import frontend_base_url


# Matches frontend: gradient-hero + primary (indigo/blue family)
_GRADIENT = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
_BG_PAGE = "#f1f5f9"
_BG_CARD = "#ffffff"
_BORDER = "#e2e8f0"
_TEXT = "#0f172a"
_TEXT_MUTED = "#64748b"
_PRIMARY_BTN = "#2563eb"
_ACCENT_BADGE = "#eff6ff"


def esc(s: Optional[str]) -> str:
    """Escape text for HTML email body."""
    if s is None:
        return ""
    return html.escape(str(s), quote=True)


def nl2br(s: Optional[str]) -> str:
    """Escape and convert newlines to <br/>."""
    if not s:
        return ""
    return esc(s).replace("\n", "<br/>\n")


def _host_label(url: str) -> str:
    try:
        p = urlparse(url)
        return p.netloc or "eRepairing"
    except Exception:
        return "eRepairing"


def wrap_branded_html(
    *,
    title: str,
    preheader: str,
    inner_html: str,
    show_footer: bool = True,
) -> str:
    """
    Full HTML document: header bar (eR + eRepairing.com), white card body, footer.
    """
    base = frontend_base_url()
    footer_link = base or "https://erepairing.com"
    host = _host_label(footer_link)

    pre = esc(preheader)[:200]
    safe_title = esc(title)

    footer_block = ""
    if show_footer:
        footer_block = f"""
        <tr>
          <td style="padding:24px 16px 8px;text-align:center;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:12px;line-height:1.5;color:{_TEXT_MUTED};">
            You received this email because you have an account with <strong style="color:{_TEXT};">{esc(host)}</strong>.<br/>
            <a href="{esc(footer_link)}" style="color:{_PRIMARY_BTN};text-decoration:none;">Visit website</a>
            &nbsp;·&nbsp;
            <span style="color:{_TEXT_MUTED};">© eRepairing</span>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>{safe_title}</title>
</head>
<body style="margin:0;padding:0;background-color:{_BG_PAGE};-webkit-font-smoothing:antialiased;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{pre}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_BG_PAGE};padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;">
          <tr>
            <td style="background:{_GRADIENT};border-radius:14px 14px 0 0;padding:22px 24px;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="width:44px;height:44px;background:#ffffff;border-radius:10px;text-align:center;vertical-align:middle;font-weight:800;font-size:15px;color:#667eea;line-height:44px;">eR</td>
                  <td style="padding-left:14px;vertical-align:middle;">
                    <span style="font-size:20px;font-weight:700;color:#ffffff;letter-spacing:-0.02em;">eRepairing</span>
                    <span style="font-size:20px;font-weight:500;color:rgba(255,255,255,0.9);">.com</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background:{_BG_CARD};border:1px solid {_BORDER};border-top:0;border-radius:0 0 14px 14px;padding:32px 28px;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:15px;line-height:1.6;color:{_TEXT};">
              {inner_html}
            </td>
          </tr>
          {footer_block}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def block_heading(text: str) -> str:
    return f"""
      <h1 style="margin:0 0 8px;font-size:22px;font-weight:700;color:{_TEXT};letter-spacing:-0.02em;">{esc(text)}</h1>"""


def block_subtitle(text: str) -> str:
    return f"""
      <p style="margin:0 0 24px;font-size:15px;color:{_TEXT_MUTED};line-height:1.55;">{esc(text)}</p>"""


def block_paragraph(text: str) -> str:
    return f"""
      <p style="margin:0 0 16px;font-size:15px;color:{_TEXT};line-height:1.6;">{esc(text)}</p>"""


def block_html_paragraph(html_safe_inner: str) -> str:
    """Inner must already be escaped where needed."""
    return f"""
      <p style="margin:0 0 16px;font-size:15px;color:{_TEXT};line-height:1.6;">{html_safe_inner}</p>"""


def block_otp(code: str) -> str:
    c = esc(code)
    return f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
        <tr>
          <td align="center" style="background:{_ACCENT_BADGE};border:1px solid #bfdbfe;border-radius:12px;padding:20px 16px;">
            <p style="margin:0 0 8px;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{_PRIMARY_BTN};">Verification code</p>
            <p style="margin:0;font-size:32px;font-weight:800;letter-spacing:0.35em;color:{_TEXT};font-family:'Segoe UI',system-ui,monospace;">{c}</p>
          </td>
        </tr>
      </table>"""


def button_primary(href: str, label: str) -> str:
    return f"""
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0;">
        <tr>
          <td align="center" style="border-radius:10px;background:{_PRIMARY_BTN};">
            <a href="{esc(href)}" target="_blank" rel="noopener noreferrer"
               style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;border-radius:10px;">
              {esc(label)}
            </a>
          </td>
        </tr>
      </table>"""


def link_fallback(url: str) -> str:
    """Plain URL for clients where the CTA button fails."""
    return f"""
      <p style="margin:20px 0 6px;font-size:12px;font-weight:600;color:{_TEXT_MUTED};text-transform:uppercase;letter-spacing:0.04em;">
        If the button doesn't work, paste this link:
      </p>
      <p style="margin:0 0 8px;font-size:13px;line-height:1.5;word-break:break-all;color:{_PRIMARY_BTN};">
        <a href="{esc(url)}" style="color:{_PRIMARY_BTN};text-decoration:underline;">{esc(url)}</a>
      </p>"""


def block_info_table(rows: list[tuple[str, str]]) -> str:
    rows_html = ""
    for k, v in rows:
        rows_html += f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid {_BORDER};font-size:13px;font-weight:600;color:{_TEXT_MUTED};width:38%;vertical-align:top;">{esc(k)}</td>
          <td style="padding:10px 12px;border-bottom:1px solid {_BORDER};font-size:14px;color:{_TEXT};vertical-align:top;">{esc(v)}</td>
        </tr>"""
    return f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;border:1px solid {_BORDER};border-radius:10px;overflow:hidden;">
        {rows_html}
      </table>"""


def block_callout(text: str, *, variant: str = "info") -> str:
    bg = "#f8fafc"
    border = _BORDER
    accent = _PRIMARY_BTN
    if variant == "warning":
        bg = "#fff7ed"
        border = "#fed7aa"
        accent = "#ea580c"
    elif variant == "success":
        bg = "#f0fdf4"
        border = "#bbf7d0"
        accent = "#16a34a"
    return f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
        <tr>
          <td style="background:{bg};border-left:4px solid {accent};border-radius:0 8px 8px 0;padding:14px 16px;font-size:14px;color:{_TEXT};line-height:1.55;border:1px solid {border};border-left-width:4px;">
            {esc(text)}
          </td>
        </tr>
      </table>"""


def block_steps_html(items: list[str]) -> str:
    lis = "".join(f'<li style="margin:8px 0;color:{_TEXT};">{esc(i)}</li>' for i in items)
    return f"""
      <ol style="margin:16px 0;padding-left:20px;color:{_TEXT};font-size:15px;line-height:1.55;">
        {lis}
      </ol>"""
