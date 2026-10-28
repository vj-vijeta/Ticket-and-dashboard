import streamlit as st
import pandas as pd
import smtplib
import random
import requests
import json
import base64
import os
import pymongo
from datetime import datetime
from email.message import EmailMessage

# --- PAGE SETUP ---
st.set_page_config(page_title="Ei | VJ Workspace", page_icon="🌊", layout="wide")

# --- SECURE CREDENTIALS ---
try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
    SENDER_PWD = st.secrets["SENDER_PWD"]
    SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "vijeta@ei.study")
    
    # GitHub Credentials
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]
    GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
    
    ZOHO_SMTP = "smtp.zoho.in"
    
    # MongoDB Database Settings
    MONGO_URI = st.secrets.get("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB_NAME = st.secrets.get("MONGO_DB_NAME", "vj_workspace_db")
except Exception:
    st.error("⚠️ Secrets not found! Please configure your Streamlit Secrets in the Cloud Dashboard or .streamlit/secrets.toml.")
    st.stop()

COLOR_BRAND = "#0284c7"
TICKET_JSON = "tickets_db.json"
DIRECTORY_JSON = "directory_db.json"
USERS_JSON = "users_db.json"

COLLECTION_MAP = {
    TICKET_JSON: "tickets",
    "tickets": "tickets",
    DIRECTORY_JSON: "directory",
    "directory": "directory",
    USERS_JSON: "users",
    "users": "users"
}

# --- DATABASE ENGINE (MONGODB PRIMARY) ---
@st.cache_resource
def get_mongo_client():
    return pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)

def get_db():
    return get_mongo_client()[MONGO_DB_NAME]

# --- DEFAULT SEED USERS ---
DEFAULT_USERS = [
    {
        "id": "USR-1001",
        "name": "Vijeta",
        "email": "vijeta@ei.study",
        "role": "Administrator & Lead",
        "portal_password": "user123",
        "email_password": SENDER_PWD,
        "status": "Active"
    }
]

# --- DATA ACCESS & REPOSITORY ENGINE ---
def get_github_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

def load_data(filename):
    """
    Fetches data directly from MongoDB (Primary Database).
    Falls back to local file / GitHub / defaults if MongoDB is initializing.
    """
    col_name = COLLECTION_MAP.get(filename, filename)
    try:
        db = get_db()
        docs = list(db[col_name].find({}, {"_id": 0}))
        if docs:
            # Sync to local backup JSON
            if filename.endswith(".json"):
                try:
                    with open(filename, 'w') as f:
                        json.dump(docs, f, indent=4)
                except Exception:
                    pass
            return docs
    except Exception as e:
        st.sidebar.warning(f"MongoDB Read Notice: {e}")

    # Fallback to local file
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                if data:
                    try:
                        db = get_db()
                        db[col_name].delete_many({})
                        db[col_name].insert_many([dict(d) for d in data])
                    except Exception:
                        pass
                return data
        except Exception:
            pass

    # Fallback to GitHub
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}?ref={GITHUB_BRANCH}"
    try:
        response = requests.get(url, headers=get_github_headers(), timeout=5)
        if response.status_code == 200:
            data = response.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            parsed = json.loads(content)
            # Sync to MongoDB and local
            try:
                db = get_db()
                db[col_name].delete_many({})
                if parsed:
                    db[col_name].insert_many([dict(d) for d in parsed])
                with open(filename, 'w') as f:
                    json.dump(parsed, f, indent=4)
            except Exception:
                pass
            return parsed
    except Exception:
        pass

    # Default seeding for users if neither DB nor files exist
    if filename == USERS_JSON or col_name == "users":
        save_data(DEFAULT_USERS, USERS_JSON)
        return DEFAULT_USERS

    return []

def save_data(data, filename):
    """
    Persists data directly to MongoDB (Primary Database),
    writes local backup copy, and pushes secondary commit to GitHub.
    """
    col_name = COLLECTION_MAP.get(filename, filename)
    
    # 1. Primary Save: MongoDB Database
    try:
        db = get_db()
        col = db[col_name]
        col.delete_many({})
        if data:
            col.insert_many([dict(d) for d in data])
    except Exception as e:
        st.sidebar.error(f"MongoDB Save Error: {e}")

    # 2. Local Backup Cache
    if filename.endswith(".json"):
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

        # 3. Secondary Backup: Push commit to GitHub
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
        headers = get_github_headers()
        
        sha = None
        try:
            get_response = requests.get(url + f"?ref={GITHUB_BRANCH}", headers=headers, timeout=5)
            if get_response.status_code == 200:
                sha = get_response.json().get("sha")
                
            content_b64 = base64.b64encode(json.dumps(data, indent=4).encode('utf-8')).decode('utf-8')
            
            payload = {
                "message": f"Auto-sync {filename} to GitHub from MongoDB via VJ Workspace App",
                "content": content_b64,
                "branch": GITHUB_BRANCH
            }
            if sha:
                payload["sha"] = sha
                
            requests.put(url, headers=headers, json=payload, timeout=8)
        except Exception:
            pass

def generate_short_id(prefix="VJ"):
    return f"{prefix}-{random.randint(1000, 9999)}"

# --- MULTI-USER EMAIL ENGINE ---
def send_mail(to_email, subject, body, cc_emails="", from_email=None, from_pwd=None):
    """
    Sends an email using either:
    1. The specified user's own email and SMTP password (if provided)
    2. Fallback to Admin/System credentials (SENDER_EMAIL / SENDER_PWD)
    """
    if not to_email:
        return False, "No recipient specified."
        
    sender = from_email if (from_email and from_pwd) else SENDER_EMAIL
    pwd = from_pwd if (from_email and from_pwd) else SENDER_PWD
    
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to_email if isinstance(to_email, str) else ", ".join(to_email)
    if cc_emails:
        msg['Cc'] = cc_emails if isinstance(cc_emails, str) else ", ".join(cc_emails)
        
    try:
        with smtplib.SMTP_SSL(ZOHO_SMTP, 465, timeout=12) as server:
            server.login(sender, pwd)
            server.send_message(msg)
        return True, f"Email sent successfully from {sender}."
    except Exception as e:
        # If user-specific credentials failed, fallback to admin/system credentials
        if sender != SENDER_EMAIL:
            try:
                msg['From'] = f"{sender} <{SENDER_EMAIL}>"
                with smtplib.SMTP_SSL(ZOHO_SMTP, 465, timeout=12) as fb_server:
                    fb_server.login(SENDER_EMAIL, SENDER_PWD)
                    fb_server.send_message(msg)
                return True, f"Sent via system fallback (user auth notice: {e})."
            except Exception as fe:
                return False, f"⚠️ Mail Error: {str(e)} (Fallback: {str(fe)})"
        return False, f"⚠️ Mail Error: {str(e)}"

# User lookup helpers
def get_user_by_name(user_name, users_list):
    for u in users_list:
        if u.get('name') == user_name:
            return u
    return None

def get_user_email_by_name(user_name, users_list):
    u = get_user_by_name(user_name, users_list)
    return u.get('email', '') if u else ''

# --- UI SETUP & CSS ---
st.markdown(f"""
    <style>
        .ei-header-banner {{ position: fixed; top: 0; left: 0; width: 100%; height: 8px; background-color: {COLOR_BRAND}; z-index: 999999; }}
        .ei-footer-banner {{ position: fixed; bottom: 0; left: 0; width: 100%; background-color: {COLOR_BRAND}; color: #FFFFFF; text-align: center; padding: 12px 0; z-index: 999999; font-family: sans-serif; font-size: 14px; box-shadow: 0 -2px 10px rgba(0,0,0,0.1); letter-spacing: 0.5px; }}
        .main .block-container {{ padding-bottom: 90px !important; padding-top: 35px !important; }}
        div.stButton > button:first-child {{ border-radius: 6px; border: 1px solid {COLOR_BRAND}; color: {COLOR_BRAND}; transition: all 0.3s; }}
        div.stButton > button:first-child:hover {{ background-color: {COLOR_BRAND}; color: white; }}
        .portal-card {{ background-color: #f8fafc; border-radius: 8px; padding: 16px; border: 1px solid #e2e8f0; margin-bottom: 12px; }}
        .notif-box {{ background-color: #f1f5f9; border-left: 4px solid {COLOR_BRAND}; padding: 10px 14px; border-radius: 4px; margin: 10px 0; }}
    </style>
    <div class="ei-header-banner"></div>
    <div class="ei-footer-banner">
        <strong>Ei</strong> | VJ Applications & Impact Dashboards &copy; {datetime.now().year}
    </div>
""", unsafe_allow_html=True)

# --- SESSION STATES ---
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False
if 'user_auth' not in st.session_state:
    st.session_state.user_auth = None

# --- SIDEBAR NAVIGATION (REORDERED: DIRECTORY FIRST, THEN REQUEST) ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency-systems-regular/96/0284c7/dashboard-layout.png", width=50)
    st.title("Workspace Nav")
    page = st.radio(
        "Go to:",
        ["App & Dashboard Directory", "Submit Request", "User Portal", "Admin Portal"]
    )
    st.divider()

    # Database Status Indicator
    try:
        db_conn = get_db()
        db_conn.command("ping")
        st.caption(f"🍃 **Database**: MongoDB (`{MONGO_DB_NAME}`)")
    except Exception as e:
        st.caption("⚠️ **Database**: Local Fallback Mode")

    # Session Status Indicators
    if st.session_state.admin_auth:
        st.success("🔒 Admin Mode Active")
        st.caption("Role: **Administrator**")
        if st.button("Logout Admin", use_container_width=True):
            st.session_state.admin_auth = False
            st.rerun()

    if st.session_state.user_auth:
        u_info = st.session_state.user_auth
        st.info(f"👤 User: **{u_info.get('name', 'User')}**\n\nEmail: `{u_info.get('email', '')}`")
        if st.button("Logout User", use_container_width=True):
            st.session_state.user_auth = None
            st.rerun()

# ==========================================
# PAGE 1: APP & DASHBOARD DIRECTORY (ENHANCED UI)
# ==========================================
if page == "App & Dashboard Directory":
    st.header("🌟 Existing Apps & Dashboards")
    st.caption("Discover, explore, and access live production tools, impact dashboards, and campaign platforms.")
    
    directory = load_data(DIRECTORY_JSON)
    
    if not directory:
        st.info("No projects showcased yet. Check back soon!")
    else:
        # Overview Metric Cards
        total_items = len(directory)
        app_count = sum(1 for d in directory if d.get('type') == 'Application')
        dash_count = sum(1 for d in directory if 'Dashboard' in d.get('type', ''))
        campaign_count = sum(1 for d in directory if 'Campaign' in d.get('type', '') or 'Content' in d.get('type', ''))
        other_count = total_items - app_count - dash_count - campaign_count
        
        stat_c1, stat_c2, stat_c3, stat_c4 = st.columns(4)
        stat_c1.metric("🚀 Total Live Tools", total_items)
        stat_c2.metric("📱 Applications", app_count)
        stat_c3.metric("📊 Analytics & Dashboards", dash_count)
        stat_c4.metric("🎨 Campaigns & Media", campaign_count if campaign_count > 0 else other_count)
        
        st.write("")
        
        # Search and Category Filter Toolbar
        sf_col1, sf_col2 = st.columns([2.5, 1.5])
        with sf_col1:
            search_query = st.text_input("🔍 Search by title, keywords, or description", placeholder="Type keywords e.g. school, attendance, sales, campaign...").strip().lower()
        with sf_col2:
            all_known_cats = ["All", "Application", "Dashboard for School", "Internal Dashboard", "Content & Campaign", "Other"]
            # Keep unique categories present in directory or standard set
            found_cats = sorted(list(set([d.get('type', 'Other') for d in directory])))
            category_options = ["All"] + [c for c in all_known_cats if c in found_cats or c == "All"]
            for c in found_cats:
                if c not in category_options:
                    category_options.append(c)
            selected_cat = st.selectbox("Category Filter", category_options)
            
        # Filter Logic
        filtered = directory
        if selected_cat != "All":
            filtered = [d for d in filtered if d.get('type') == selected_cat]
        if search_query:
            filtered = [
                d for d in filtered
                if search_query in d.get('title', '').lower()
                or search_query in d.get('description', '').lower()
                or search_query in d.get('usage', '').lower()
            ]
            
        st.caption(f"Showing **{len(filtered)}** of **{total_items}** tools")
        st.divider()
        
        if not filtered:
            st.warning("🔍 No apps or dashboards matched your search criteria. Try a different keyword or category.")
        else:
            cat_styles = {
                "Application": ("#dbeafe", "#1e40af", "📱"),
                "Dashboard for School": ("#dcfce7", "#166534", "🎓"),
                "Internal Dashboard": ("#f3e8ff", "#6b21a8", "📊"),
                "Content & Campaign": ("#fef3c7", "#92400e", "🎨"),
                "Other": ("#f1f5f9", "#475569", "⚡")
            }
            
            cols = st.columns(2)
            for idx, item in enumerate(filtered):
                with cols[idx % 2]:
                    title = item.get('title', 'Untitled Tool')
                    cat = item.get('type', 'Other')
                    desc = item.get('description', 'No description provided.')
                    usage = item.get('usage', 'No usage instructions provided.')
                    url = item.get('url', '')
                    
                    bg_col, text_col, icon = cat_styles.get(cat, ("#f1f5f9", "#475569", "⚡"))
                    
                    with st.container(border=True):
                        # Card Header with Category Pill
                        header_html = f"""
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                            <h3 style="margin: 0; font-size: 1.15rem; color: #1e293b; font-weight: 700;">{title}</h3>
                            <span style="background-color: {bg_col}; color: {text_col}; padding: 3px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; white-space: nowrap; margin-left: 8px;">
                                {icon} {cat}
                            </span>
                        </div>
                        """
                        st.markdown(header_html, unsafe_allow_html=True)
                        st.markdown(f"<p style='color: #475569; font-size: 0.92rem; line-height: 1.5; min-height: 48px; margin-bottom: 14px;'>{desc}</p>", unsafe_allow_html=True)
                        
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if url:
                                st.link_button("🚀 Launch Live", url, use_container_width=True)
                            else:
                                st.button("🔒 Internal Tool", disabled=True, use_container_width=True, key=f"btn_internal_{idx}_{title}")
                        with btn_col2:
                            with st.popover("📖 How to Use", use_container_width=True):
                                st.markdown(f"#### Instructions: {title}")
                                st.markdown(usage)

# ==========================================
# PAGE 2: SUBMIT REQUEST (WITH CONTENT & CAMPAIGN SUPPORT)
# ==========================================
elif page == "Submit Request":
    st.header("📩 Request Support, Campaign, or New Dashboard")
    st.caption("Submit your requirements for dashboards, creative posters, marketing campaigns, or technical assistance.")
    
    users = load_data(USERS_JSON)
    active_users = [u['name'] for u in users if u.get('status', 'Active') == 'Active']
    assign_options = ["Unassigned"] + active_users
    
    # SUPPORT TYPES INCLUDING CONTENT CREATION, POSTERS, AND CAMPAIGNS
    SUPPORT_TYPES = [
        # Content & Campaign Support
        "Poster & Creative Graphic Design",
        "Content Creation & Copywriting",
        "Email Campaign Setup & Broadcast",
        "WhatsApp Campaign & Automation",
        "Social Media & Marketing Campaign",
        "Video / Multimedia Editing",
        # Dashboard & Technical Support
        "New Dashboard Creation",
        "Existing Dashboard Modification",
        "Data Extraction & SQL Help",
        "Bug / Error Resolution",
        "Consultation & System Architecture",
        "Other / Custom Request"
    ]
    
    with st.form("ticket_form", clear_on_submit=False):
        st.subheader("1. Requester Details")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Your Name*")
        with col2:
            email = st.text_input("Your Work Email*")
        
        st.subheader("2. Request Context & Assignment")
        col3, col4, col5 = st.columns([1.6, 1.1, 1.3])
        with col3:
            req_type = st.selectbox(
                "Type of Support Needed*",
                SUPPORT_TYPES,
                help="Select the exact type of support needed, including creative posters, marketing campaigns, or dashboards."
            )
        with col4:
            urgency = st.selectbox("Initial Priority*", ["Low", "Medium", "High", "Critical"])
        with col5:
            # ASSIGN TO OPTION
            assigned_to = st.selectbox(
                "Assign To*",
                options=assign_options,
                index=0,
                help="Route this task to a specific team member, or leave as Unassigned."
            )
            
        url = st.text_input("Reference Asset / Design / Application URL (If any)", placeholder="https://drive.google.com/..., https://figma.com/..., etc.")
        
        # CHANGED FROM "Technical Details" TO "Details"
        st.subheader("3. Details")
        requirements = st.text_area(
            "Specific Requirements*",
            placeholder="e.g., Target audience, key messaging, dimensions, visual style, copy requirements, or dashboard metrics...",
            height=100
        )
        desc = st.text_area(
            "Detailed Description / Use Case*",
            placeholder="Explain the background, deliverables required, deadlines, context, or why this request is needed...",
            height=100
        )
        
        # 4. PERSON DECIDES WHOM THE MAIL GOES TO (ADMIN EMAIL HIDDEN)
        st.subheader("4. 📬 Notification Preferences (Decide Who Receives Email)")
        st.caption("Choose exactly who receives email notifications for this request:")
        
        c_n1, c_n2, c_n3 = st.columns(3)
        with c_n1:
            send_to_requester = st.checkbox("Notify Requester (You)", value=True, help="Send confirmation email to your email address.")
        with c_n2:
            send_to_assignee = st.checkbox("Notify Assigned Person", value=True, help="Send alert email to the selected team member.")
        with c_n3:
            send_to_admin = st.checkbox("Notify Admin", value=True, help="Send alert to the workspace administrator.")
            
        extra_cc = st.text_input("Additional CC Recipients (Optional, comma-separated email addresses)", placeholder="colleague1@ei.study, manager@ei.study")
        
        submit_btn = st.form_submit_button("Submit Request", use_container_width=True)
        
        if submit_btn:
            if name and "@" in email and requirements and desc:
                t_id = generate_short_id()
                p_map = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}
                
                # Fetch live data, append, and save
                tickets = load_data(TICKET_JSON)
                
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                ticket = {
                    "id": t_id,
                    "name": name,
                    "email": email,
                    "type": req_type,
                    "priority": p_map[urgency],
                    "priority_str": urgency,
                    "url": url,
                    "requirements": requirements,
                    "description": desc,
                    "assigned_to": assigned_to,
                    "assigned_history": [
                        {
                            "assigned_to": assigned_to,
                            "assigned_by": name,
                            "timestamp": now_str,
                            "note": "Initial request submission"
                        }
                    ],
                    "status": "Open",
                    "timestamp": now_str
                }
                
                tickets.append(ticket)
                with st.spinner("Saving ticket..."):
                    save_data(tickets, TICKET_JSON)
                
                # SENDER DETERMINATION:
                # "when assigned to some one the confirmation must go from their id"
                # If assigned to a team member with their own credentials, send confirmation from their ID!
                assigned_user_obj = get_user_by_name(assigned_to, users) if assigned_to != "Unassigned" else None
                
                confirmation_from_email = None
                confirmation_from_pwd = None
                confirmation_sender_name = "Admin / Ei Workspace"
                
                if assigned_user_obj and assigned_user_obj.get('email'):
                    confirmation_from_email = assigned_user_obj.get('email')
                    confirmation_from_pwd = assigned_user_obj.get('email_password', '')
                    confirmation_sender_name = assigned_to
                else:
                    confirmation_from_email = SENDER_EMAIL
                    confirmation_from_pwd = SENDER_PWD
                    confirmation_sender_name = "Ei Workspace Admin"

                # 1. Send confirmation to Requester (from the assigned person's ID)
                if send_to_requester:
                    if assigned_to != "Unassigned":
                        user_mail_content = (
                            f"Hi {name},\n\n"
                            f"Your request {t_id} ({req_type}) has been assigned to me ({assigned_to}).\n"
                            f"I have received your request and will review the requirements shortly.\n\n"
                            f"Priority: {urgency}\n"
                            f"Requirements:\n{requirements}\n\n"
                            f"Description:\n{desc}\n\n"
                            f"Best regards,\n{assigned_to}\n{confirmation_from_email}"
                        )
                    else:
                        user_mail_content = (
                            f"Hi {name},\n\n"
                            f"Your request {t_id} ({req_type}) has been successfully logged with Ei Workspace.\n"
                            f"Status: Open (Unassigned - undergoing triage)\n\n"
                            f"We will review your requirements shortly and keep you updated.\n\n"
                            f"Best regards,\nEi Workspace Team"
                        )
                    send_mail(
                        email,
                        f"Ticket Logged: {t_id} - {req_type}",
                        user_mail_content,
                        cc_emails=extra_cc,
                        from_email=confirmation_from_email,
                        from_pwd=confirmation_from_pwd
                    )
                
                # 2. Send notification to Assignee
                if send_to_assignee and assigned_user_obj and assigned_user_obj.get('email'):
                    assignee_email = assigned_user_obj.get('email')
                    assignee_content = (
                        f"Hi {assigned_to},\n\n"
                        f"A new task {t_id} has been assigned to you by {name} ({email}).\n\n"
                        f"Type: {req_type}\nPriority: {urgency}\n\n"
                        f"Requirements:\n{requirements}\n\nDescription:\n{desc}\n\n"
                        f"Please log in to your User Portal to track progress or reassign if needed."
                    )
                    send_mail(
                        assignee_email,
                        f"New Task Assigned to You: {t_id}",
                        assignee_content,
                        cc_emails=extra_cc,
                        from_email=SENDER_EMAIL,
                        from_pwd=SENDER_PWD
                    )
                
                # 3. Send alert to Admin
                if send_to_admin:
                    admin_alert_content = (
                        f"🚨 NEW TICKET RECEIVED 🚨\n\nID: {t_id}\nFrom: {name} ({email})\n"
                        f"Assigned To: {assigned_to}\nPriority: {urgency}\nType: {req_type}\n\n"
                        f"Requirements:\n{requirements}\n\nDescription:\n{desc}"
                    )
                    send_mail(
                        SENDER_EMAIL,
                        f"New Ticket Alert: {t_id} - {urgency} (Assigned: {assigned_to})",
                        admin_alert_content,
                        cc_emails=extra_cc,
                        from_email=SENDER_EMAIL,
                        from_pwd=SENDER_PWD
                    )
                
                st.success(f"Ticket **{t_id}** submitted successfully and assigned to **{assigned_to}**! Confirmation sent from **{confirmation_from_email}**.")
                st.balloons()
            else:
                st.error("Please fill in all mandatory fields (*).")

# ==========================================
# PAGE 3: USER PORTAL
# ==========================================
elif page == "User Portal":
    users = load_data(USERS_JSON)
    
    # Check if user is logged in
    if not st.session_state.user_auth:
        st.header("👤 User Portal Access")
        st.caption("Log in with your team credentials to view assigned tasks, update progress, and reassign tasks.")
        
        col_l1, col_l2 = st.columns([1.2, 1])
        with col_l1:
            with st.container(border=True):
                st.subheader("Login to Your Dashboard")
                user_options = [u['name'] for u in users if u.get('status', 'Active') == 'Active']
                
                if not user_options:
                    st.warning("No active users found in the system. Please ask an Admin to create users in the Admin Portal.")
                else:
                    sel_user_name = st.selectbox("Select Your Name", user_options)
                    entered_pwd = st.text_input("Enter Portal Password", type="password")
                    
                    if st.button("Log In to Portal", use_container_width=True):
                        user_match = next((u for u in users if u.get('name') == sel_user_name), None)
                        expected_pwd = user_match.get('portal_password') or user_match.get('password', '')
                        if user_match and expected_pwd == entered_pwd:
                            st.session_state.user_auth = user_match
                            st.success(f"Welcome back, {sel_user_name}!")
                            st.rerun()
                        else:
                            st.error("Incorrect password. Please verify your credentials or contact the Administrator.")
        with col_l2:
            st.info("""
            **💡 User Portal Features:**
            - **Personal Email Identity:** Send task confirmations and updates directly from your own email address and credentials.
            - **Custom Notification Routing:** Decide exactly who receives email notifications (Requester, Admin, Colleague, or custom CC).
            - **Track & Reassign:** Update progress notes or reassign tasks seamlessly to another team member.
            """)
    else:
        # User is logged in
        current_user = st.session_state.user_auth
        # Re-fetch latest user record from DB
        matched = next((u for u in users if u.get('id') == current_user.get('id') or u.get('name') == current_user.get('name')), current_user)
        current_user = matched
        st.session_state.user_auth = current_user
        
        user_name = current_user.get('name', 'User')
        user_email = current_user.get('email', '')
        user_email_pwd = current_user.get('email_password', '')
        
        c_head1, c_head2 = st.columns([4, 1])
        with c_head1:
            st.header(f"👤 Welcome, {user_name}")
            auth_badge = "✅ Email Sender Configured" if user_email_pwd else "⚠️ Using System Sender (Add Email Pwd in Profile)"
            st.caption(f"Role: **{current_user.get('role', 'Team Member')}** | Email: `{user_email}` | {auth_badge}")
        with c_head2:
            if st.button("🚪 Logout User", use_container_width=True):
                st.session_state.user_auth = None
                st.rerun()

        tickets = load_data(TICKET_JSON)
        
        # Filter tickets assigned to this user
        my_tickets = [t for t in tickets if t.get('assigned_to') == user_name]
        my_active = [t for t in my_tickets if t.get('status') not in ['Closed', 'Resolved']]
        my_closed = [t for t in my_tickets if t.get('status') in ['Closed', 'Resolved']]
        my_critical = [t for t in my_active if str(t.get('priority')) in ['1', '2']]
        
        # Key Performance Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📌 Active Tasks", len(my_active))
        m2.metric("⚡ Critical / High Priority", len(my_critical))
        m3.metric("✅ Completed Tasks", len(my_closed))
        m4.metric("📁 Total Assigned", len(my_tickets))
        
        st.divider()
        
        tab_my_tasks, tab_reassign, tab_profile, tab_all_team = st.tabs([
            "📋 My Tasks & Status", "🔄 Reassign Tasks", "⚙️ My Profile & Email Credentials", "🌐 Team Tasks Overview"
        ])
        
        # --- SUB-TAB 1: MY TASKS & STATUS UPDATE ---
        with tab_my_tasks:
            st.subheader(f"Tasks Assigned to {user_name}")
            
            if not my_tickets:
                st.info("You currently have no tasks assigned to you. When new requests are assigned, they will appear here.")
            else:
                view_mode = st.radio("Show Tasks:", ["Active Queue", "Closed / Archive"], horizontal=True)
                subset = my_active if view_mode == "Active Queue" else my_closed
                
                if subset:
                    df_my = pd.DataFrame(subset)
                    color_map = {1: "🔴 1-Critical", 2: "🟠 2-High", 3: "🟡 3-Medium", 4: "🟢 4-Low", "1": "🔴 1-Critical", "2": "🟠 2-High", "3": "🟡 3-Medium", "4": "🟢 4-Low"}
                    df_my['Priority Level'] = df_my['priority'].map(color_map)
                    
                    display_cols = ["id", "Priority Level", "status", "type", "name", "timestamp"]
                    st.dataframe(df_my[display_cols], use_container_width=True, hide_index=True)
                else:
                    st.write(f"No {view_mode.lower()} tasks found.")
                    
                st.divider()
                st.subheader("Update Task Status & Notes")
                
                if my_active:
                    tid_to_update = st.selectbox("Select Task to Update", [t['id'] for t in my_active], key="user_update_tid")
                    current_t = next(t for t in tickets if t['id'] == tid_to_update)
                    
                    with st.expander(f"🔍 Task Details for {tid_to_update} - {current_t.get('type')}", expanded=True):
                        st.markdown(f"**Requester:** {current_t.get('name')} ({current_t.get('email')})")
                        st.markdown(f"**Requirements:** {current_t.get('requirements', 'N/A')}")
                        st.markdown(f"**Description:** {current_t.get('description', 'N/A')}")
                        if current_t.get('url'):
                            st.markdown(f"**Reference URL:** [{current_t['url']}]({current_t['url']})")
                        
                        hist = current_t.get('assigned_history', [])
                        if hist:
                            st.caption("📜 Assignment History:")
                            for h in hist:
                                st.caption(f"- {h.get('timestamp')}: To **{h.get('assigned_to', h.get('to'))}** (Note: {h.get('note', h.get('reason', 'N/A'))})")
                    
                    col_u1, col_u2 = st.columns(2)
                    with col_u1:
                        curr_status = current_t.get('status', 'Open')
                        status_choices = ["Open", "In Progress", "Closed"]
                        s_idx = status_choices.index(curr_status) if curr_status in status_choices else 0
                        new_user_status = st.selectbox("New Status", status_choices, index=s_idx)
                    with col_u2:
                        user_note = st.text_input("Progress / Status Note for Requester")
                        
                    # PERSON DECIDES WHOM THE MAIL GOES TO
                    st.markdown("##### 📬 Notification Routing (Decide Who Receives Email)")
                    col_notif1, col_notif2, col_notif3 = st.columns([1.2, 1.2, 1.6])
                    with col_notif1:
                        u_send_to_req = st.checkbox("Notify Requester", value=True, key="unotif_req")
                    with col_notif2:
                        u_send_to_admin = st.checkbox("Notify Admin", value=False, key="unotif_adm")
                    with col_notif3:
                        u_custom_cc = st.text_input("Additional CC Recipients", key="unotif_cc", placeholder="e.g. colleague@ei.study")
                        
                    if st.button("Update Status & Send Notification", use_container_width=True):
                        old_s = current_t.get('status', 'Open')
                        current_t['status'] = new_user_status
                        
                        with st.spinner("Saving task update..."):
                            save_data(tickets, TICKET_JSON)
                            
                        req_email = current_t.get('email')
                        req_name = current_t.get('name', 'User')
                        note_text = f"\n\n**Note from {user_name}:**\n{user_note}" if user_note else ""
                        status_body = (
                            f"Hi {req_name},\n\n"
                            f"Your request {tid_to_update} status has been updated to '{new_user_status}' by {user_name}.{note_text}\n\n"
                            f"Best regards,\n{user_name}\n{user_email}"
                        )
                        
                        # Send to Requester (From the user's own email ID)
                        if u_send_to_req and req_email:
                            send_mail(
                                req_email,
                                f"Task Update: {tid_to_update} ({new_user_status})",
                                status_body,
                                cc_emails=u_custom_cc,
                                from_email=user_email,
                                from_pwd=user_email_pwd
                            )
                            
                        # Send to Admin if selected
                        if u_send_to_admin:
                            admin_body = (
                                f"User Status Update for Task: {tid_to_update}\n"
                                f"Updated by: {user_name} ({user_email})\n"
                                f"New Status: {new_user_status}\n"
                                f"Requester: {req_name} ({req_email}){note_text}"
                            )
                            send_mail(
                                SENDER_EMAIL,
                                f"Status Update Notice: {tid_to_update} - {new_user_status}",
                                admin_body,
                                cc_emails=u_custom_cc,
                                from_email=user_email,
                                from_pwd=user_email_pwd
                            )
                            
                        st.success(f"Status for {tid_to_update} updated to '{new_user_status}'! Emails dispatched from **{user_email or 'Workspace System'}**.")
                        st.rerun()
                else:
                    st.info("No active tasks to update.")

        # --- SUB-TAB 2: REASSIGN TASKS ---
        with tab_reassign:
            st.subheader("🔄 Reassign Task to Another Team Member")
            st.caption("Hand off or reassign a task that is currently assigned to you.")
            
            if not my_active:
                st.info("You do not have any active tasks to reassign.")
            else:
                reassign_tid = st.selectbox("Select Task to Reassign", [t['id'] for t in my_active], key="reassign_select")
                selected_ticket = next(t for t in tickets if t['id'] == reassign_tid)
                
                colleague_options = [u['name'] for u in users if u.get('name') != user_name and u.get('status', 'Active') == 'Active']
                
                if not colleague_options:
                    st.warning("No other active colleagues found in the user directory to reassign to.")
                else:
                    col_r1, col_r2 = st.columns(2)
                    with col_r1:
                        st.markdown(f"**Task ID:** `{reassign_tid}`")
                        st.markdown(f"**Requester:** {selected_ticket.get('name')} ({selected_ticket.get('email')})")
                        st.markdown(f"**Type:** {selected_ticket.get('type')}")
                        st.markdown(f"**Current Priority:** {selected_ticket.get('priority_str', 'Normal')}")
                    with col_r2:
                        target_user = st.selectbox("Reassign To Colleague*", colleague_options)
                        reassign_reason = st.text_area(
                            "Reason for Reassignment / Handover Notes*",
                            placeholder="e.g., Transferring for data extraction and dashboard refinement..."
                        )
                        
                    # PERSON DECIDES WHOM THE MAIL GOES TO
                    st.markdown("##### 📬 Notification Routing (Decide Who Receives Email)")
                    col_rn1, col_rn2, col_rn3 = st.columns(3)
                    with col_rn1:
                        r_send_to_new = st.checkbox("Notify New Assignee", value=True, key="r_notif_new")
                    with col_rn2:
                        r_send_to_req = st.checkbox("Notify Requester", value=True, key="r_notif_req")
                    with col_rn3:
                        r_send_to_admin = st.checkbox("Notify Admin", value=True, key="r_notif_adm")
                    r_extra_cc = st.text_input("Additional CC Recipients", key="r_notif_cc", placeholder="e.g. manager@ei.study")
                        
                    if st.button("Confirm & Reassign Task", use_container_width=True):
                        if not reassign_reason.strip():
                            st.error("Please provide a reason or note for reassigning this task.")
                        else:
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                            
                            # Update ticket assignment
                            selected_ticket['assigned_to'] = target_user
                            if 'assigned_history' not in selected_ticket:
                                selected_ticket['assigned_history'] = []
                            selected_ticket['assigned_history'].append({
                                "assigned_to": target_user,
                                "assigned_by": user_name,
                                "timestamp": now_str,
                                "note": reassign_reason
                            })
                            
                            with st.spinner("Committing reassignment..."):
                                save_data(tickets, TICKET_JSON)
                                
                            target_user_obj = get_user_by_name(target_user, users)
                            target_email = target_user_obj.get('email') if target_user_obj else ''
                            
                            # 1. Notify new assignee (From current user's email ID)
                            if r_send_to_new and target_email:
                                new_assignee_content = (
                                    f"Hi {target_user},\n\n"
                                    f"Task {reassign_tid} ({selected_ticket.get('type')}) has been reassigned to you by {user_name}.\n\n"
                                    f"Handover Notes:\n{reassign_reason}\n\n"
                                    f"Original Requester: {selected_ticket.get('name')} ({selected_ticket.get('email')})\n"
                                    f"Requirements:\n{selected_ticket.get('requirements')}\n\n"
                                    f"Please check your User Portal to track and manage."
                                )
                                send_mail(
                                    target_email,
                                    f"Task Reassigned to You: {reassign_tid}",
                                    new_assignee_content,
                                    cc_emails=r_extra_cc,
                                    from_email=user_email,
                                    from_pwd=user_email_pwd
                                )
                                
                            # 2. Notify requester of reassignment (From current user's email ID)
                            req_email = selected_ticket.get('email')
                            if r_send_to_req and req_email:
                                req_content = (
                                    f"Hi {selected_ticket.get('name')},\n\n"
                                    f"Your request {reassign_tid} has been reassigned to {target_user} by {user_name}.\n\n"
                                    f"Handover Reason: {reassign_reason}\n\n"
                                    f"Best regards,\n{user_name}\n{user_email}"
                                )
                                send_mail(
                                    req_email,
                                    f"Assignment Update: {reassign_tid}",
                                    req_content,
                                    cc_emails=r_extra_cc,
                                    from_email=user_email,
                                    from_pwd=user_email_pwd
                                )
                                
                            # 3. Notify Admin if selected
                            if r_send_to_admin:
                                admin_reassign_content = (
                                    f"Task Reassignment Notice: {reassign_tid}\n\n"
                                    f"Reassigned from: {user_name} ({user_email})\n"
                                    f"Reassigned to: {target_user} ({target_email})\n"
                                    f"Reason: {reassign_reason}\n"
                                    f"Requester: {selected_ticket.get('name')} ({req_email})"
                                )
                                send_mail(
                                    SENDER_EMAIL,
                                    f"Task Reassigned: {reassign_tid} -> {target_user}",
                                    admin_reassign_content,
                                    cc_emails=r_extra_cc,
                                    from_email=user_email,
                                    from_pwd=user_email_pwd
                                )
                                
                            st.success(f"Task **{reassign_tid}** successfully reassigned to **{target_user}**! Notifications dispatched from **{user_email or 'Workspace System'}**.")
                            st.rerun()

        # --- SUB-TAB 3: MY PROFILE & EMAIL CREDENTIALS ---
        with tab_profile:
            st.subheader("⚙️ My Profile & Email Credentials")
            st.caption("Configure your personal work email and Zoho App Password so that all task confirmations and reassignments are sent directly from your own email account.")
            
            with st.form("my_profile_form"):
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    my_name_disp = st.text_input("Name", value=current_user.get('name', ''), disabled=True)
                    my_email_val = st.text_input("Your Work Email*", value=current_user.get('email', ''))
                    my_portal_pwd = st.text_input("User Portal Password*", value=current_user.get('portal_password') or current_user.get('password', 'user123'), type="password")
                with col_p2:
                    my_email_pwd = st.text_input(
                        "Your Zoho / Email App Password",
                        value=current_user.get('email_password', ''),
                        type="password",
                        help="Enter your Zoho account App Password to authenticate SMTP and send emails directly from your email address."
                    )
                    st.caption("ℹ️ *If left blank, the workspace default admin sender will be used as a fallback.*")
                
                col_save, col_test = st.columns([1, 1])
                with col_save:
                    save_profile_btn = st.form_submit_button("💾 Save Profile & Credentials", use_container_width=True)
                with col_test:
                    test_email_btn = st.form_submit_button("🧪 Test Email Connection", use_container_width=True)
                    
                if save_profile_btn:
                    if my_email_val.strip() and "@" in my_email_val and my_portal_pwd.strip():
                        current_user['email'] = my_email_val.strip()
                        current_user['portal_password'] = my_portal_pwd.strip()
                        current_user['email_password'] = my_email_pwd.strip()
                        
                        # Update in users list
                        for idx, u in enumerate(users):
                            if u.get('id') == current_user.get('id'):
                                users[idx] = current_user
                                break
                        with st.spinner("Saving profile..."):
                            save_data(users, USERS_JSON)
                        st.session_state.user_auth = current_user
                        st.success("Your profile and email credentials have been updated!")
                        st.rerun()
                    else:
                        st.error("Please provide a valid email and portal password.")
                        
                if test_email_btn:
                    if my_email_val.strip() and my_email_pwd.strip():
                        test_ok, test_msg = send_mail(
                            my_email_val.strip(),
                            "Ei Workspace - SMTP Test",
                            f"Hi {my_name_disp},\n\nThis is a test email verifying that your personal email credentials ({my_email_val.strip()}) work properly for sending task notifications.\n\nAll systems nominal!",
                            from_email=my_email_val.strip(),
                            from_pwd=my_email_pwd.strip()
                        )
                        if test_ok:
                            st.success(f"Connection test succeeded! A test message was sent to {my_email_val}.")
                        else:
                            st.error(f"Test failed: {test_msg}")
                    else:
                        st.warning("Please enter your Work Email and Email App Password before running the connection test.")

        # --- SUB-TAB 4: TEAM TASKS OVERVIEW ---
        with tab_all_team:
            st.subheader("🌐 Team Workload & Requests")
            st.caption("High-level overview of team allocations across all active tickets.")
            
            if tickets:
                df_all = pd.DataFrame(tickets)
                if 'assigned_to' not in df_all.columns:
                    df_all['assigned_to'] = 'Unassigned'
                df_all['assigned_to'] = df_all['assigned_to'].fillna('Unassigned')
                
                workload = df_all.groupby('assigned_to').agg(
                    Total_Tickets=('id', 'count'),
                    Active_Tickets=('status', lambda x: sum(~x.isin(['Closed', 'Resolved'])))
                ).reset_index().sort_values(by='Active_Tickets', ascending=False)
                
                st.dataframe(workload, hide_index=True, use_container_width=True)
            else:
                st.info("No tickets logged in the workspace.")

# ==========================================
# PAGE 4: ADMIN PORTAL (WITH USER MANAGEMENT & NOTIFICATION CONTROLS)
# ==========================================
else:
    if not st.session_state.admin_auth:
        st.subheader("Admin Access")
        st.caption("Secure workspace authentication for Administrators.")
        pw = st.text_input("Enter Workspace Password", type="password")
        if st.button("Secure Login"):
            if pw == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("Access Denied. Incorrect Password.")
    else:
        # 4 TABS: Tickets, Leaderboard, User Management, Directory
        tab_tickets, tab_leader, tab_users, tab_port = st.tabs([
            "🎫 Manage Tickets", "📊 Leaderboard & Workload", "👥 User Management", "🌟 Manage Directory"
        ])
        
        tickets = load_data(TICKET_JSON)
        users = load_data(USERS_JSON)
        
        # --- TAB 1: TICKETS ---
        with tab_tickets:
            if tickets:
                df = pd.DataFrame(tickets)
                color_map = {1: "🔴 1-Critical", 2: "🟠 2-High", 3: "🟡 3-Medium", 4: "🟢 4-Low", "1": "🔴 1-Critical", "2": "🟠 2-High", "3": "🟡 3-Medium", "4": "🟢 4-Low"}
                
                df['priority'] = df['priority'].astype(str)
                df['Priority Level'] = df['priority'].map(color_map)
                if 'assigned_to' not in df.columns:
                    df['assigned_to'] = 'Unassigned'
                df['assigned_to'] = df['assigned_to'].fillna('Unassigned')
                
                selected_priorities = st.multiselect(
                    "Filter by Priority:",
                    options=["🔴 1-Critical", "🟠 2-High", "🟡 3-Medium", "🟢 4-Low"],
                    default=["🔴 1-Critical", "🟠 2-High", "🟡 3-Medium", "🟢 4-Low"]
                )
                df_filtered = df[df['Priority Level'].isin(selected_priorities)].sort_values("priority")
                view_cols = ["id", "Priority Level", "status", "assigned_to", "type", "name", "timestamp"]
                
                active_tab, closed_tab = st.tabs(["🟢 Active Queue", "🔘 Closed / Archive"])
                
                with active_tab:
                    df_active = df_filtered[~df_filtered['status'].isin(['Closed', 'Resolved'])]
                    if not df_active.empty:
                        st.dataframe(df_active[view_cols], use_container_width=True, hide_index=True)
                    else:
                        st.info("No active tickets match the current filter.")
                        
                with closed_tab:
                    df_closed = df_filtered[df_filtered['status'].isin(['Closed', 'Resolved'])]
                    if not df_closed.empty:
                        st.dataframe(df_closed[view_cols], use_container_width=True, hide_index=True)
                    else:
                        st.info("No closed tickets match the current filter.")

                st.divider()
                st.subheader("Update / Triage & Assign Ticket")
                active_tickets = [t for t in tickets if t.get('status') not in ['Closed', 'Resolved']]
                
                if active_tickets:
                    tid = st.selectbox("Select Ticket ID to Triage", [t['id'] for t in active_tickets])
                    current_t = next(t for t in tickets if t['id'] == tid)
                    
                    with st.expander(f"Review Details for {tid} ({current_t.get('name', 'Unknown')})"):
                        st.write(f"**Requirements:** {current_t.get('requirements', 'N/A')}")
                        st.write(f"**Description:** {current_t.get('description', 'N/A')}")
                        if current_t.get('url'):
                            st.write(f"**URL:** {current_t['url']}")
                        curr_hist = current_t.get('assigned_history', [])
                        if curr_hist:
                            st.write("**Assignment History:**")
                            for h in curr_hist:
                                st.write(f"- {h.get('timestamp')}: **{h.get('assigned_to', h.get('to'))}** (By {h.get('assigned_by', h.get('by', 'System'))} - {h.get('note', h.get('reason', ''))})")
                    
                    col_u1, col_u2, col_u3 = st.columns(3)
                    with col_u1:
                        new_p = st.number_input("Adjust Priority (1=Critical, 4=Low)", 1, 4, value=int(current_t.get('priority', 4)))
                    with col_u2:
                        current_status = current_t.get('status', 'Open')
                        if current_status == 'Resolved':
                            current_status = 'Closed' 
                        status_options = ["Open", "In Progress", "De-prioritized", "Closed"]
                        safe_index = status_options.index(current_status) if current_status in status_options else 0
                        new_s = st.selectbox("Update Status", status_options, index=safe_index)
                    with col_u3:
                        # ADMIN ASSIGN / REASSIGN OPTION
                        current_assigned = current_t.get('assigned_to', 'Unassigned')
                        user_list = ["Unassigned"] + [u['name'] for u in users if u.get('status', 'Active') == 'Active']
                        assign_idx = user_list.index(current_assigned) if current_assigned in user_list else 0
                        new_assigned = st.selectbox("Assign / Reassign To", user_list, index=assign_idx)
                    
                    st.write("**Communication Options & Notification Routing:**")
                    admin_comments = st.text_area("Admin Comments (Included in user email)")
                    deprio_reason = st.text_area("Reason for De-prioritization*") if new_s == "De-prioritized" else ""
                    
                    # PERSON DECIDES WHOM THE MAIL GOES TO
                    st.markdown("##### 📬 Who Should Receive Emails?")
                    col_an1, col_an2, col_an3 = st.columns(3)
                    with col_an1:
                        adm_notify_req = st.checkbox("Notify Requester", value=True, key="adm_notif_req")
                    with col_an2:
                        adm_notify_assignee = st.checkbox("Notify Assigned Member", value=True, key="adm_notif_ass")
                    with col_an3:
                        adm_notify_admin = st.checkbox("Send Copy to Admin", value=False, key="adm_notif_adm")
                    cc_recipients = st.text_input("Additional CC Recipients (Comma-separated emails)")
                    
                    if st.button("Update Ticket & Send Notifications", use_container_width=True):
                        if new_s == "De-prioritized" and not deprio_reason:
                            st.error("You must provide a reason to de-prioritize.")
                        else:
                            old_s = current_t.get('status', 'Open')
                            old_assigned = current_t.get('assigned_to', 'Unassigned')
                            user_email = current_t.get('email', '')
                            requester_name = current_t.get('name', 'User')
                            comment_block = f"\n\n**Admin Notes:**\n{admin_comments}" if admin_comments else ""
                            
                            # Check if assignment changed
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                            if new_assigned != old_assigned:
                                if 'assigned_history' not in current_t:
                                    current_t['assigned_history'] = []
                                current_t['assigned_history'].append({
                                    "assigned_to": new_assigned,
                                    "assigned_by": "Administrator",
                                    "timestamp": now_str,
                                    "note": f"Reassigned by Admin from {old_assigned}"
                                })
                            
                            # Update DB values
                            for t in tickets:
                                if t['id'] == tid:
                                    t['status'] = new_s
                                    t['priority'] = new_p
                                    t['assigned_to'] = new_assigned
                                    
                            with st.spinner("Committing changes to GitHub..."):
                                save_data(tickets, TICKET_JSON)
                            
                            # Notifications to Requester (From Admin: vijeta@ei.study)
                            if adm_notify_req and user_email:
                                if old_s != "In Progress" and new_s == "In Progress":
                                    send_mail(user_email, f"Work Started: {tid}", f"Hi {requester_name},\n\nWork has officially started on request {tid} (Assigned: {new_assigned}). Expect updates soon!{comment_block}", cc_recipients, from_email=SENDER_EMAIL, from_pwd=SENDER_PWD)
                                elif new_s == "De-prioritized" and old_s != "De-prioritized":
                                    send_mail(user_email, f"Status Update: {tid}", f"Hi {requester_name},\n\nRegarding request {tid}:\n\nThis task has been temporarily de-prioritized.\nReason: {deprio_reason}{comment_block}", cc_recipients, from_email=SENDER_EMAIL, from_pwd=SENDER_PWD)
                                elif new_s == "Closed" and old_s not in ["Closed", "Resolved"]:
                                    send_mail(user_email, f"Resolved & Closed: {tid}", f"Hi {requester_name},\n\nYour request {tid} has been officially resolved and closed!{comment_block}", cc_recipients, from_email=SENDER_EMAIL, from_pwd=SENDER_PWD)
                                elif admin_comments:
                                    send_mail(user_email, f"Ticket Update: {tid}", f"Hi {requester_name},\n\nAn update has been added to your request {tid}:{comment_block}", cc_recipients, from_email=SENDER_EMAIL, from_pwd=SENDER_PWD)

                            # Notification to newly assigned user if assignment changed
                            if adm_notify_assignee and new_assigned != old_assigned and new_assigned != "Unassigned":
                                target_user_obj = get_user_by_name(new_assigned, users)
                                target_email = target_user_obj.get('email') if target_user_obj else ''
                                if target_email:
                                    send_mail(
                                        target_email,
                                        f"Task Assigned by Admin: {tid}",
                                        f"Hi {new_assigned},\n\nAdministrator has assigned task {tid} to you.\n\nPriority: {new_p}\nRequester: {requester_name}{comment_block}\n\nPlease check your User Portal to manage.",
                                        cc_recipients,
                                        from_email=SENDER_EMAIL,
                                        from_pwd=SENDER_PWD
                                    )

                            # Send copy to admin if chosen
                            if adm_notify_admin:
                                send_mail(
                                    SENDER_EMAIL,
                                    f"Admin Update Copy: {tid} ({new_s})",
                                    f"Admin updated ticket {tid}.\nStatus: {new_s}\nAssigned To: {new_assigned}\nRequester: {requester_name}{comment_block}",
                                    cc_recipients,
                                    from_email=SENDER_EMAIL,
                                    from_pwd=SENDER_PWD
                                )

                            st.success(f"Ticket {tid} successfully updated! Assigned to: {new_assigned}.")
                            st.rerun()
            else:
                st.info("Your queue is entirely empty.")

        # --- TAB 2: ENHANCED LEADERBOARD & WORKLOAD ---
        with tab_leader:
            st.subheader("📊 Requesters & Team Allocation Breakdown")
            
            if tickets:
                df = pd.DataFrame(tickets)
                if 'assigned_to' not in df.columns:
                    df['assigned_to'] = 'Unassigned'
                df['assigned_to'] = df['assigned_to'].fillna('Unassigned')
                
                col_lead1, col_lead2 = st.columns(2)
                with col_lead1:
                    st.markdown("#### 🏆 Top Requesters")
                    if 'name' in df.columns:
                        leaderboard = df.groupby('name').agg(
                            Tickets_Submitted=('id', 'count'),
                            Active_Tickets=('status', lambda x: sum(~x.isin(['Closed', 'Resolved'])))
                        ).reset_index().sort_values(by='Tickets_Submitted', ascending=False)
                        st.dataframe(leaderboard, hide_index=True, use_container_width=True)
                
                with col_lead2:
                    st.markdown("#### 👥 Team Workload Distribution")
                    team_dist = df.groupby('assigned_to').agg(
                        Total_Assigned=('id', 'count'),
                        Active_Tasks=('status', lambda x: sum(~x.isin(['Closed', 'Resolved'])))
                    ).reset_index().sort_values(by='Active_Tasks', ascending=False)
                    st.dataframe(team_dist, hide_index=True, use_container_width=True)
                    
                st.divider()
                st.markdown("### 📋 Detailed Ticket View by Requester")
                for _, row in leaderboard.iterrows():
                    user_req_name = row['name']
                    with st.expander(f"👤 {user_req_name} ({row['Tickets_Submitted']} Total Tickets)"):
                        user_tickets = df[df['name'] == user_req_name][['id', 'priority_str', 'status', 'assigned_to', 'type', 'timestamp']]
                        user_tickets.columns = ['Ticket ID', 'Priority', 'Status', 'Assigned To', 'Request Type', 'Submitted On']
                        st.dataframe(user_tickets, hide_index=True, use_container_width=True)
            else:
                st.info("No tickets to analyze yet.")

        # --- TAB 3: USER MANAGEMENT SYSTEM ---
        with tab_users:
            st.subheader("👥 User Management System")
            st.caption("Manage team members, roles, passwords, and task assignment availability.")
            
            # Overview KPIs
            active_count = sum(1 for u in users if u.get('status', 'Active') == 'Active')
            inactive_count = len(users) - active_count
            
            u_col1, u_col2, u_col3 = st.columns(3)
            u_col1.metric("Total Users", len(users))
            u_col2.metric("Active Users", active_count)
            u_col3.metric("Inactive / On Leave", inactive_count)
            
            st.divider()
            
            user_mgmt_action = st.radio("Choose Action:", ["All Team Users", "➕ Add New User", "✏️ Edit / Deactivate User"], horizontal=True)
            
            # Sub-view 1: All Users
            if user_mgmt_action == "All Team Users":
                if users:
                    df_u = pd.DataFrame(users)
                    # Show safe columns (no raw passwords)
                    display_user_cols = ["id", "name", "email", "role", "status"]
                    display_user_cols = [c for c in display_user_cols if c in df_u.columns]
                    st.dataframe(df_u[display_user_cols], use_container_width=True, hide_index=True)
                else:
                    st.info("No users registered yet.")
                    
            # Sub-view 2: Add New User
            elif user_mgmt_action == "➕ Add New User":
                st.markdown("#### Create New Team Member Profile")
                with st.form("add_user_form", clear_on_submit=True):
                    col_nu1, col_nu2 = st.columns(2)
                    with col_nu1:
                        new_u_name = st.text_input("Full Name*")
                        new_u_email = st.text_input("User's Work Email*")
                        new_u_role = st.selectbox(
                            "Role / Title*",
                            ["Developer", "Senior Developer / Analyst", "Data Analyst", "Support Specialist", "Project Manager", "Administrator & Lead", "Other"]
                        )
                    with col_nu2:
                        new_u_portal_pwd = st.text_input("Portal Login Password*", value="user123", help="Password used to sign in to User Portal.")
                        new_u_email_pwd = st.text_input("Zoho / Email App Password (Optional)", type="password", help="User's Zoho app password for sending task notifications directly from their email address.")
                        new_u_status = st.selectbox("Initial Status", ["Active", "Inactive"])
                    
                    if st.form_submit_button("Create User & Save", use_container_width=True):
                        if new_u_name.strip() and "@" in new_u_email and new_u_portal_pwd.strip():
                            # Check duplicates
                            if any(u.get('name', '').lower() == new_u_name.strip().lower() for u in users):
                                st.error(f"A user named '{new_u_name}' already exists.")
                            elif any(u.get('email', '').lower() == new_u_email.strip().lower() for u in users):
                                st.error(f"A user with email '{new_u_email}' already exists.")
                            else:
                                new_uid = generate_short_id(prefix="USR")
                                new_user_obj = {
                                    "id": new_uid,
                                    "name": new_u_name.strip(),
                                    "email": new_u_email.strip(),
                                    "role": new_u_role,
                                    "portal_password": new_u_portal_pwd.strip(),
                                    "email_password": new_u_email_pwd.strip(),
                                    "status": new_u_status
                                }
                                users.append(new_user_obj)
                                with st.spinner("Committing new user to database..."):
                                    save_data(users, USERS_JSON)
                                    
                                # Welcome email to new user (From Admin)
                                send_mail(
                                    new_u_email.strip(),
                                    "Welcome to Ei Workspace Portal",
                                    f"Hi {new_u_name},\n\nYour user profile has been created in the Ei Workspace App.\n\nRole: {new_u_role}\nYour Portal Login Password: {new_u_portal_pwd}\nYour Email Address: {new_u_email.strip()}\n\nYou can log in to the User Portal to view, update, and reassign tasks.\n\nBest regards,\nWorkspace Administrator",
                                    from_email=SENDER_EMAIL,
                                    from_pwd=SENDER_PWD
                                )
                                st.success(f"User **{new_u_name}** ({new_uid}) created successfully! Welcome email dispatched.")
                                st.rerun()
                        else:
                            st.error("Please fill in all mandatory fields with a valid email.")
                            
            # Sub-view 3: Edit / Deactivate User
            elif user_mgmt_action == "✏️ Edit / Deactivate User":
                if not users:
                    st.info("No users to edit.")
                else:
                    user_select_names = [f"{u.get('name')} ({u.get('email')})" for u in users]
                    selected_u_label = st.selectbox("Select User to Edit", user_select_names)
                    
                    sel_idx = user_select_names.index(selected_u_label)
                    target_u = users[sel_idx]
                    
                    with st.form("edit_user_form"):
                        st.caption(f"Editing User ID: **{target_u.get('id')}**")
                        col_eu1, col_eu2 = st.columns(2)
                        with col_eu1:
                            edit_name = st.text_input("Full Name*", value=target_u.get('name', ''))
                            edit_email = st.text_input("User's Work Email*", value=target_u.get('email', ''))
                            role_list = ["Developer", "Senior Developer / Analyst", "Data Analyst", "Support Specialist", "Project Manager", "Administrator & Lead", "Other"]
                            curr_role = target_u.get('role', 'Developer')
                            r_idx = role_list.index(curr_role) if curr_role in role_list else 0
                            edit_role = st.selectbox("Role / Title", role_list, index=r_idx)
                        with col_eu2:
                            edit_portal_pwd = st.text_input("User Portal Password*", value=target_u.get('portal_password') or target_u.get('password', 'user123'), type="password")
                            edit_email_pwd = st.text_input("Zoho / Email App Password", value=target_u.get('email_password', ''), type="password")
                            status_list = ["Active", "Inactive"]
                            curr_stat = target_u.get('status', 'Active')
                            s_idx = status_list.index(curr_stat) if curr_stat in status_list else 0
                            edit_status = st.selectbox("Status", status_list, index=s_idx)
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            save_u_btn = st.form_submit_button("💾 Update User Profile")
                        with col_btn2:
                            del_u_btn = st.form_submit_button("🗑️ Delete User")
                            
                        if save_u_btn:
                            if edit_name.strip() and "@" in edit_email and edit_portal_pwd.strip():
                                old_user_name = target_u.get('name')
                                target_u['name'] = edit_name.strip()
                                target_u['email'] = edit_email.strip()
                                target_u['role'] = edit_role
                                target_u['portal_password'] = edit_portal_pwd.strip()
                                target_u['email_password'] = edit_email_pwd.strip()
                                target_u['status'] = edit_status
                                
                                # If name changed, update tickets assigned to old name
                                if old_user_name != edit_name.strip():
                                    for t in tickets:
                                        if t.get('assigned_to') == old_user_name:
                                            t['assigned_to'] = edit_name.strip()
                                    save_data(tickets, TICKET_JSON)
                                    
                                with st.spinner("Saving user changes..."):
                                    save_data(users, USERS_JSON)
                                    
                                st.success(f"Profile for **{edit_name}** updated successfully!")
                                st.rerun()
                            else:
                                st.error("Please fill in valid Name, Email, and Password.")
                                
                        if del_u_btn:
                            deleted_name = target_u.get('name')
                            # Check if user has active tickets
                            active_assigned = [t['id'] for t in tickets if t.get('assigned_to') == deleted_name and t.get('status') not in ['Closed', 'Resolved']]
                            if active_assigned:
                                st.warning(f"Note: {deleted_name} was assigned to active tickets ({', '.join(active_assigned)}). These have been marked Unassigned.")
                                for t in tickets:
                                    if t.get('assigned_to') == deleted_name:
                                        t['assigned_to'] = "Unassigned"
                                save_data(tickets, TICKET_JSON)
                                
                            users.pop(sel_idx)
                            with st.spinner("Deleting user..."):
                                save_data(users, USERS_JSON)
                            st.success(f"User **{deleted_name}** deleted.")
                            st.rerun()

        # --- TAB 4: MANAGE DIRECTORY ---
        with tab_port:
            st.subheader("Manage App & Dashboard Directory")
            dir_action = st.radio("Choose Action:", ["Publish New Application", "Edit / Delete Existing"], horizontal=True)
            
            directory = load_data(DIRECTORY_JSON)
            
            if dir_action == "Publish New Application":
                with st.form("directory_form", clear_on_submit=True):
                    p_title = st.text_input("Name*")
                    p_type = st.selectbox("Category", ["Application", "Dashboard for School", "Internal Dashboard", "Content & Campaign", "Other"])
                    p_url = st.text_input("Live URL")
                    p_desc = st.text_area("Short Description*")
                    p_usage = st.text_area("Usage Instructions")
                    
                    if st.form_submit_button("Publish to Directory"):
                        if p_title and p_desc:
                            directory.append({"title": p_title, "type": p_type, "url": p_url, "description": p_desc, "usage": p_usage})
                            with st.spinner("Committing to GitHub..."):
                                save_data(directory, DIRECTORY_JSON)
                            st.success("Successfully added to your public directory!")
                        else:
                            st.error("Name and Description are required.")
                            
            elif dir_action == "Edit / Delete Existing":
                if not directory:
                    st.info("The directory is currently empty.")
                else:
                    app_names = [app.get('title', 'Untitled') for app in directory]
                    selected_app = st.selectbox("Select Application to Edit", app_names)
                    
                    app_idx = next((i for i, item in enumerate(directory) if item.get('title') == selected_app), None)
                    
                    if app_idx is not None:
                        curr_app = directory[app_idx]
                        st.caption(f"Editing: **{curr_app.get('title')}**")
                        
                        with st.form("edit_dir_form"):
                            e_title = st.text_input("Name*", value=curr_app.get('title', ''))
                            categories = ["Application", "Dashboard for School", "Internal Dashboard", "Content & Campaign", "Other"]
                            curr_cat = curr_app.get('type', 'Other')
                            cat_index = categories.index(curr_cat) if curr_cat in categories else 4
                            
                            e_type = st.selectbox("Category", categories, index=cat_index)
                            e_url = st.text_input("Live URL", value=curr_app.get('url', ''))
                            e_desc = st.text_area("Short Description*", value=curr_app.get('description', ''))
                            e_usage = st.text_area("Usage Instructions", value=curr_app.get('usage', ''))
                            
                            col_e1, col_e2 = st.columns(2)
                            with col_e1:
                                update_btn = st.form_submit_button("💾 Update Details")
                            with col_e2:
                                delete_btn = st.form_submit_button("🗑️ Delete Application")
                                
                            if update_btn:
                                if e_title and e_desc:
                                    directory[app_idx] = {"title": e_title, "type": e_type, "url": e_url, "description": e_desc, "usage": e_usage}
                                    with st.spinner("Committing changes to GitHub..."):
                                        save_data(directory, DIRECTORY_JSON)
                                    st.success(f"Updated '{e_title}' successfully!")
                                    st.rerun()
                                else:
                                    st.error("Name and Description are required.")
                            
                            if delete_btn:
                                directory.pop(app_idx)
                                with st.spinner("Removing from GitHub..."):
                                    save_data(directory, DIRECTORY_JSON)
                                st.success(f"Deleted '{selected_app}' from the directory.")
                                st.rerun()
