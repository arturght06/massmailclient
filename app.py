import os
import imaplib
import email
import json
from email.header import decode_header
from flask import Flask, render_template, request, jsonify
from models import db_session, Account, Email
from init.init_db import init_db

app = Flask(__name__)

with open(os.path.join(os.path.dirname(__file__), 'DOMAIN_MAP.json'), 'r') as f:
    DOMAIN_MAP = json.load(f)

def get_imap_server(email_addr):
    try:
        domain = email_addr.split('@')[1].lower().strip()
        if domain in DOMAIN_MAP:
            return DOMAIN_MAP[domain]
        return f"imap.{domain}"
    except IndexError:
        return None

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

def check_connection_and_login(server, email_user, password):
    try:
        mail = imaplib.IMAP4_SSL(server, 993)
        mail.login(email_user, password)
        mail.logout()
        return True, "OK"
    except Exception as e:
        return False, str(e)

def sync_account_emails(account_id, limit=10):
    account = db_session.get(Account, account_id)
    if not account:
        return {"status": "error", "message": "Account not found"}

    try:
        mail = imaplib.IMAP4_SSL(account.imap_server, account.imap_port)
        mail.login(account.email, account.password)
        mail.select("inbox")

        status, messages = mail.search(None, "ALL")
        if status != "OK":
            return {"status": "error", "message": "Search failed"}

        mail_ids = messages[0].split()
        latest_ids = mail_ids[-limit:]
        new_emails_count = 0

        for i in reversed(latest_ids):
            uid = i.decode()
            exists = db_session.query(Email).filter_by(account_id=account_id, imap_uid=uid).first()
            if exists:
                continue

            res, msg_data = mail.fetch(i, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")

                    sender = msg.get("From")
                    body = "No text content"
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode(errors="ignore")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode(errors="ignore")

                    try:
                        email_obj = Email(
                            account_id=account_id,
                            imap_uid=uid,
                            subject=subject,
                            sender=sender,
                            body=body
                        )
                        db_session.add(email_obj)
                        new_emails_count += 1
                    except Exception:
                        pass

        account.status = 'active'
        db_session.commit()
        mail.logout()
        return {"status": "success", "new_count": new_emails_count}
    except Exception as e:
        account.status = 'error'
        db_session.commit()
        return {"status": "error", "message": str(e)}

# --- Routes ---
@app.route('/')
def index():
    accounts = db_session.query(Account).all()
    return render_template('index.html', accounts=accounts)

@app.route('/search', methods=['POST'])
def search_accounts():
    query = request.json.get("query", "").strip()
    accounts = db_session.query(Account).filter(Account.email.like(f"%{query}%")).all()

    if accounts:
        return jsonify({
            "status": "success",
            "accounts": [
                {
                    "id": acc.id,
                    "email": acc.email,
                    "imap_server": acc.imap_server,
                    "imap_port": acc.imap_port,
                    "password": acc.password,
                    "status": acc.status,
                } for acc in accounts
            ]
        })
    else:
        return jsonify({"status": "error", "message": "No accounts found"})


@app.route('/get_account_details/<int:account_id>')
def get_account_details(account_id):
    account = db_session.get(Account, account_id)
    if not account:
        return jsonify({"status": "error", "message": "Account not found"}), 404

    return jsonify({
        "id": account.id,
        "email": account.email,
        "imap_server": account.imap_server,
        "imap_port": account.imap_port,
        "status": account.status,
        "notes": account.notes,
        "proxy": account.proxy,
        "password": account.password
    })

@app.route('/update_account/<int:account_id>', methods=['POST'])
def update_account(account_id):
    data = request.json
    email_user = data['email']
    password = data['password']
    server = data['imap_server']

    is_valid, msg = check_connection_and_login(server, email_user, password)

    status = 'active' if is_valid else 'error'

    try:
        account = db_session.get(Account, account_id)
        if not account:
            return jsonify({"status": "error", "message": "Account not found"})
        account.email = email_user
        account.password = password
        account.imap_server = server
        account.status = status
        db_session.commit()

        if is_valid:
            return jsonify({"status": "success", "message": "Updated & Verified!"})
        else:
            return jsonify({"status": "warning", "message": f"Updated, but login failed: {msg}"})
    except Exception as e:
        db_session.rollback()
        return jsonify({"status": "error", "message": str(e)})

@app.route('/delete_account/<int:account_id>', methods=['POST'])
def delete_account(account_id):
    account = db_session.get(Account, account_id)
    if not account:
        return jsonify({"status": "error", "message": "Account not found"})
    db_session.delete(account)
    db_session.commit()
    return jsonify({"status": "success"})

@app.route('/get_cached_emails/<int:account_id>')
def get_cached_emails(account_id):
    emails = db_session.query(Email).filter_by(account_id=account_id).order_by(Email.id.desc()).limit(50).all()
    return jsonify([
        {
            "id": e.id,
            "subject": e.subject,
            "sender": e.sender,
            "body": e.body,
            "imap_uid": e.imap_uid,
            "date_str": e.date_str
        } for e in emails
    ])

@app.route('/sync_emails/<int:account_id>', methods=['POST'])
def sync_route(account_id):
    res = sync_account_emails(account_id)
    return jsonify(res)

@app.route('/bulk_import', methods=['POST'])
def bulk_import():
    raw_text = request.json.get('data', '')
    lines = raw_text.strip().split('\n')
    added_ids = []
    for line in lines:
        if ':' not in line:
            continue
        parts = line.split(':', 1)
        email_addr = parts[0].strip()
        password = parts[1].strip()
        server = get_imap_server(email_addr)
        try:
            account = Account(
                email=email_addr,
                password=password,
                imap_server=server if server else 'unknown',
                status='pending'
            )
            db_session.add(account)
            db_session.flush()  # get id before commit
            added_ids.append({"id": account.id, "email": email_addr})
        except Exception:
            db_session.rollback()
    db_session.commit()
    return jsonify({"added": added_ids})

@app.route('/check_account_status/<int:account_id>')
def check_status(account_id):
    account = db_session.get(Account, account_id)
    if not account:
        return jsonify({"status": "deleted"})
    is_valid, msg = check_connection_and_login(account.imap_server, account.email, account.password)
    new_status = 'active' if is_valid else 'error'
    account.status = new_status
    db_session.commit()
    return jsonify({"status": new_status, "msg": msg})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', debug=True, port=8080)
