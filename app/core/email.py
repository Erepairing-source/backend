"""
Email sending service (SMTP).
All HTML bodies use the branded layout (see email_templates) aligned with the website UI.
"""
import logging
from urllib.parse import quote
import smtplib
from email.utils import formataddr, make_msgid, formatdate
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import settings
logger = logging.getLogger(__name__)

from app.core.email_templates import (
    block_callout,
    block_heading,
    block_html_paragraph,
    block_info_table,
    block_otp,
    block_paragraph,
    block_steps_html,
    block_subtitle,
    button_primary,
    link_fallback,
    nl2br,
    wrap_branded_html,
)


def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
) -> bool:
    """
    Send an email via SMTP.
    Returns True on success, False if SMTP is not configured or send fails.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning(
            "SMTP not configured (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD). Email to %s not sent.",
            to_email,
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    if settings.SMTP_REPLY_TO:
        msg["Reply-To"] = settings.SMTP_REPLY_TO

    if body_text:
        msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        use_ssl = getattr(settings, "SMTP_USE_SSL", False)
        if use_ssl:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if getattr(settings, "SMTP_USE_TLS", True):
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
        logger.info("SMTP sent ok subject=%r to=%s", subject, to_email)
        return True
    except Exception as e:
        logger.exception("SMTP send failed to %s: %s", to_email, e)
        return False


def send_credentials_email(
    to_email: str,
    full_name: Optional[str],
    password: str,
    login_url: Optional[str] = None,
    email_verification_otp: Optional[str] = None,
    verify_email_url: Optional[str] = None,
) -> bool:
    """
    Send login credentials (email + password) to the user.
    Used for bulk customer creation when Org Admin uploads Excel and opts to email credentials.
    Optionally includes a 6-digit email verification OTP and link to the verify-email page.
    """
    name = full_name or "there"
    login = login_url or (getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/") + "/login")
    base = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    verify_link = verify_email_url or f"{base}/verify-email?email={quote(to_email, safe='')}"
    otp_txt = ""
    if email_verification_otp:
        otp_txt = (
            f"\nEmail verification code (expires in 15 minutes):\n  {email_verification_otp}\n\n"
            f"Verify your email: {verify_link}\n\n"
        )
    subject = "Your eRepairing customer account"
    body_text = (
        f"Hi {name},\n\n"
        "Your customer account has been created.\n\n"
        f"Email: {to_email}\n"
        f"Password: {password}\n\n"
        f"{otp_txt}"
        f"Log in here: {login}\n\n"
        "You can change your password after logging in.\n\n"
        "— eRepairing"
    )
    inner = (
        block_heading(f"Hi {name},")
        + block_subtitle("Your customer account is ready. Use the details below to sign in.")
        + block_info_table(
            [
                ("Email", to_email),
                ("Password", password),
            ]
        )
        + block_callout("You can change your password anytime after logging in.", variant="info")
    )
    if email_verification_otp:
        inner += (
            block_paragraph("Verify your email with this code (expires in 15 minutes):")
            + block_otp(email_verification_otp)
            + button_primary(verify_link, "Verify your email")
        )
    inner += button_primary(login, "Log in to eRepairing")
    body_html = wrap_branded_html(
        title=subject,
        preheader=f"Your login details for {to_email}",
        inner_html=inner,
    )
    return send_email(to_email, subject, body_html, body_text)


def send_otp_email(
    to_email: str,
    otp_code: str,
    purpose: str,
    ticket_number: str,
    full_name: Optional[str] = None,
) -> bool:
    """
    Send OTP to customer for service start or completion verification.
    purpose: 'start' | 'completion'
    """
    name = full_name or "there"
    action = "start the service" if purpose == "start" else "confirm completion of the service"
    subject = f"Your OTP for ticket {ticket_number} – eRepairing"
    body_text = (
        f"Hi {name},\n\n"
        f"Your OTP to {action} for ticket {ticket_number} is:\n\n"
        f"  {otp_code}\n\n"
        "This OTP is valid for 10 minutes. Share it with the engineer to proceed.\n\n"
        "— eRepairing"
    )
    inner = (
        block_heading(f"Hi {name},")
        + block_subtitle(f"Your OTP to {action} for ticket {ticket_number} is below.")
        + block_otp(otp_code)
        + block_callout(
            "This code is valid for 10 minutes. Share it only with your assigned engineer.",
            variant="warning",
        )
    )
    body_html = wrap_branded_html(
        title=subject,
        preheader=f"Ticket {ticket_number} — your one-time code",
        inner_html=inner,
    )
    return send_email(to_email, subject, body_html, body_text)


def send_ticket_created_email(
    to_email: str,
    ticket_number: str,
    issue_description: str,
    priority: str,
    service_address: Optional[str],
    sla_deadline_iso: Optional[str],
    ticket_link: str,
    full_name: Optional[str] = None,
    issue_category: Optional[str] = None,
    device_label: Optional[str] = None,
) -> bool:
    """Notify customer that a ticket was created (issue summary + link)."""
    name = full_name or "there"
    addr = (service_address or "").strip() or "—"
    sla = sla_deadline_iso or "—"
    cat = (issue_category or "").strip() or "—"
    dev = (device_label or "").strip() or "—"
    subject = f"Ticket {ticket_number} created – eRepairing"
    body_text = (
        f"Hi {name},\n\n"
        f"Your service ticket has been created. We will keep you updated by email.\n\n"
        f"Ticket number: {ticket_number}\n"
        f"Priority: {priority}\n"
        f"Category: {cat}\n"
        f"Device: {dev}\n"
        f"Service address: {addr}\n"
        f"Resolution target (SLA): {sla}\n\n"
        f"Issue summary:\n{issue_description}\n\n"
        f"View your ticket: {ticket_link}\n\n"
        "— eRepairing"
    )
    inner = (
        block_heading(f"Hi {name},")
        + block_subtitle("Your service ticket has been created. We'll keep you updated by email.")
        + block_info_table(
            [
                ("Ticket", ticket_number),
                ("Priority", priority),
                ("Category", cat),
                ("Device", dev),
                ("Service address", addr),
                ("Resolution target (SLA)", sla),
            ]
        )
        + block_paragraph("Issue summary")
        + block_html_paragraph(nl2br(issue_description))
        + button_primary(ticket_link, "Open your ticket")
    )
    body_html = wrap_branded_html(
        title=subject,
        preheader=f"Ticket {ticket_number} — we're on it",
        inner_html=inner,
    )
    return send_email(to_email, subject, body_html, body_text)


def send_ticket_assigned_email(
    to_email: str,
    ticket_number: str,
    engineer_name: Optional[str],
    ticket_link: str,
    full_name: Optional[str] = None,
) -> bool:
    """Notify customer that an engineer was assigned."""
    name = full_name or "there"
    eng = engineer_name or "your engineer"
    subject = f"Engineer assigned to ticket {ticket_number} – eRepairing"
    body_text = (
        f"Hi {name},\n\n"
        f"Your ticket {ticket_number} has been assigned to {eng}.\n\n"
        f"Details: {ticket_link}\n\n"
        "— eRepairing"
    )
    inner = (
        block_heading(f"Hi {name},")
        + block_subtitle(f"Ticket {ticket_number} is now assigned to {eng}.")
        + block_callout("You'll receive another update when work begins.", variant="info")
        + button_primary(ticket_link, "View ticket")
    )
    body_html = wrap_branded_html(
        title=subject,
        preheader=f"{eng} is handling ticket {ticket_number}",
        inner_html=inner,
    )
    return send_email(to_email, subject, body_html, body_text)


def send_ticket_work_started_email(
    to_email: str,
    ticket_number: str,
    ticket_link: str,
    full_name: Optional[str] = None,
    eta_note: Optional[str] = None,
) -> bool:
    """Notify customer that work has started on the ticket."""
    name = full_name or "there"
    eta = (eta_note or "").strip()
    subject = f"Work started on ticket {ticket_number} – eRepairing"
    extra_txt = f"\n{eta}\n" if eta else "\n"
    body_text = (
        f"Hi {name},\n\n"
        f"Work has started on your ticket {ticket_number}.{extra_txt}"
        f"{ticket_link}\n\n"
        "— eRepairing"
    )
    inner = (
        block_heading(f"Hi {name},")
        + block_subtitle(f"Work has started on ticket {ticket_number}.")
    )
    if eta:
        inner += block_html_paragraph(nl2br(eta))
    inner += button_primary(ticket_link, "View ticket")
    body_html = wrap_branded_html(
        title=subject,
        preheader=f"Work in progress on ticket {ticket_number}",
        inner_html=inner,
    )
    return send_email(to_email, subject, body_html, body_text)


def send_ticket_resolved_email(
    to_email: str,
    ticket_number: str,
    resolution_notes: str,
    ticket_link: str,
    full_name: Optional[str] = None,
) -> bool:
    """Notify customer that the ticket was resolved."""
    name = full_name or "there"
    notes = (resolution_notes or "").strip() or "—"
    subject = f"Ticket {ticket_number} resolved – eRepairing"
    body_text = (
        f"Hi {name},\n\n"
        f"Your ticket {ticket_number} has been marked resolved.\n\n"
        f"Resolution notes:\n{notes}\n\n"
        f"{ticket_link}\n\n"
        "— eRepairing"
    )
    inner = (
        block_heading(f"Hi {name},")
        + block_subtitle(f"Ticket {ticket_number} is marked resolved.")
        + block_callout("Thank you for using eRepairing. We'd love your feedback if anything could be better.", variant="success")
        + block_paragraph("Resolution notes")
        + block_html_paragraph(nl2br(notes))
        + button_primary(ticket_link, "View ticket")
    )
    body_html = wrap_branded_html(
        title=subject,
        preheader=f"Ticket {ticket_number} — resolved",
        inner_html=inner,
    )
    return send_email(to_email, subject, body_html, body_text)


def send_email_verification_otp(
    to_email: str,
    otp_code: str,
    full_name: Optional[str] = None,
    context: str = "account",
) -> bool:
    """
    Send a 6-digit code to verify email ownership (signup, new user, resend).
    context: short label for the email body (e.g. 'organization signup', 'customer account').
    """
    name = full_name or "there"
    subject = "Verify your email – eRepairing"
    body_text = (
        f"Hi {name},\n\n"
        f"Your email verification code for your {context} is:\n\n"
        f"  {otp_code}\n\n"
        "Enter this code in the app to verify your email. The code expires in 15 minutes.\n\n"
        "If you did not create an account, you can ignore this email.\n\n"
        "— eRepairing"
    )
    inner = (
        block_heading(f"Hi {name},")
        + block_subtitle(f"Use this code to verify your email for your {context}.")
        + block_otp(otp_code)
        + block_paragraph("Enter the code in the app. It expires in 15 minutes.")
        + block_paragraph("If you didn't request this, you can safely ignore this email.")
    )
    body_html = wrap_branded_html(
        title=subject,
        preheader="Your verification code inside",
        inner_html=inner,
    )
    return send_email(to_email, subject, body_html, body_text)


def send_set_password_email(
    to_email: str,
    set_password_link: str,
    full_name: Optional[str] = None,
    email_verification_otp: Optional[str] = None,
) -> bool:
    """
    Send the "Set your password" email with a one-time link.
    Optionally include a 6-digit email verification OTP in the same message.
    """
    name = full_name or "there"
    subject = "Welcome to eRepairing – verify email & set your password"
    otp_block_txt = ""
    if email_verification_otp:
        otp_block_txt = (
            f"\nYour verification code (expires in 15 minutes):\n\n  {email_verification_otp}\n\n"
        )
    body_text = (
        f"Hi {name},\n\n"
        "Welcome to eRepairing.\n\n"
        f"{otp_block_txt}"
        "1) Open the link below.\n"
        "2) On that page, enter the verification code above, then your new password twice and submit.\n"
        "The link works only once.\n\n"
        f"{set_password_link}\n\n"
        "If you did not request this, you can ignore this email.\n\n"
        "— eRepairing"
    )
    inner = (
        block_heading(f"Welcome, {name}!")
        + block_subtitle("Finish setting up your eRepairing account in two quick steps.")
    )
    if email_verification_otp:
        inner += (
            block_paragraph("Your verification code (expires in 15 minutes):")
            + block_otp(email_verification_otp)
        )
    inner += (
        block_steps_html(
            [
                "Open the secure link below.",
                "Enter your verification code (if shown), then choose your password and confirm.",
            ]
        )
        + block_callout("This link works only once. If it expires, ask your admin for a new invite.", variant="warning")
        + button_primary(set_password_link, "Open account setup")
        + link_fallback(set_password_link)
        + block_paragraph("If you didn't request this, you can ignore this email.")
    )
    body_html = wrap_branded_html(
        title=subject,
        preheader="Set your password and verify your email",
        inner_html=inner,
    )
    return send_email(to_email, subject, body_html, body_text)


def send_contract_renewal_reminder_email(
    to_email: str,
    organization_name: str,
    plan_name: str,
    end_date_display: str,
    days_remaining: int,
    dashboard_url: str,
    full_name: Optional[str] = None,
) -> bool:
    """Remind organization admin that the subscription contract is ending soon."""
    name = full_name or "there"
    subject = f"Subscription renews in {days_remaining} day(s) – {organization_name}"
    body_text = (
        f"Hi {name},\n\n"
        f"This is a reminder that your eRepairing subscription for {organization_name} "
        f"({plan_name}) will end on {end_date_display} — {days_remaining} day(s) remaining.\n\n"
        "Please renew your plan before the end date to avoid interruption to service tickets, engineers, and integrations.\n\n"
        f"Open your organization dashboard: {dashboard_url}\n\n"
        "If you need help, contact your account manager or eRepairing support.\n\n"
        "— eRepairing"
    )
    inner = (
        block_heading(f"Hi {name},")
        + block_subtitle("Your eRepairing subscription is ending soon.")
        + block_info_table(
            [
                ("Organization", organization_name),
                ("Plan", plan_name),
                ("End date", end_date_display),
                ("Days remaining", str(days_remaining)),
            ]
        )
        + block_callout(
            "Renew before the end date to avoid interruption to tickets, engineers, and integrations.",
            variant="warning",
        )
        + button_primary(dashboard_url, "Open organization dashboard")
        + block_paragraph("Questions? Contact your account manager or eRepairing support.")
    )
    body_html = wrap_branded_html(
        title=subject,
        preheader=f"{days_remaining} day(s) left on {organization_name}'s plan",
        inner_html=inner,
    )
    return send_email(to_email, subject, body_html, body_text)


def send_service_visit_reminder_email(
    to_email: str,
    ticket_number: str,
    when_label: str,
    detail_line: str,
    ticket_link: str,
    full_name: Optional[str] = None,
) -> bool:
    """
    Remind customer of an upcoming service visit / follow-up.
    when_label: e.g. 'Tomorrow' or date string
    detail_line: human-readable context (follow-up date, ETA window)
    """
    name = full_name or "there"
    subject = f"Reminder: service visit for ticket {ticket_number} – eRepairing"
    body_text = (
        f"Hi {name},\n\n"
        f"Reminder: you have a scheduled service activity for ticket {ticket_number} ({when_label}).\n\n"
        f"{detail_line}\n\n"
        f"View details: {ticket_link}\n\n"
        "— eRepairing"
    )
    inner = (
        block_heading(f"Hi {name},")
        + block_subtitle(f"Reminder: service for ticket {ticket_number} — {when_label}.")
        + block_html_paragraph(nl2br(detail_line))
        + button_primary(ticket_link, "Open your ticket")
    )
    body_html = wrap_branded_html(
        title=subject,
        preheader=f"Upcoming visit — ticket {ticket_number}",
        inner_html=inner,
    )
    return send_email(to_email, subject, body_html, body_text)
