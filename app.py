import streamlit as st
import pandas as pd
import smtplib
import random
import requests
import json
import base64
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
    MOHAN_EMAIL = "mohan.kumar@ei.study"
except Exception:
    st.error("⚠️ Secrets not found! Please configure your Streamlit Secrets in the Cloud Dashboard.")
    st.stop()

COLOR_BRAND = "#0284c7"
TICKET_JSON = "tickets_db.json"
DIRECTORY_JSON = "directory_db.json"

# --- GITHUB COMMIT ENGINE ---
def get_github_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

def load_data(filename):
    """Fetches the latest JSON file directly from your GitHub repo."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}?ref={GITHUB_BRANCH}"
    try:
        response = requests.get(url, headers=get_github_headers())
        if response.status_code == 200:
            data = response.json()
            # GitHub sends file content encoded in Base64
            content = base64.b64decode(data['content']).decode('utf-8')
            return json.loads(content)
        return []
    except Exception as e:
        st.sidebar.error(f"GitHub Read Error: {e}")
        return []

def save_data(data, filename):
    """Encodes JSON to Base64 and pushes a commit to GitHub."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    headers = get_github_headers()
    
    # 1. Fetch current file to get the 'sha' (Required by GitHub to update an existing file)
    sha = None
    get_response = requests.get(url + f"?ref={GITHUB_BRANCH}", headers=headers)
    if get_response.status_code == 200:
        sha = get_response.json().get("sha")
        
    # 2. Encode our new JSON back to Base64
    content_b64 = base64.b64encode(json.dumps(data, indent=4).encode('utf-8')).decode('utf-8')
    
    # 3. Create the commit payload
    payload = {
        "message": f"Auto-update {filename} via VJ Workspace App",
        "content": content_b64,
        "branch": GITHUB_BRANCH
    }
    if sha:
        payload["sha"] = sha
        
    # 4. Push the commit
    response = requests.put(url, headers=headers, json=payload)
    if response.status_code not in [200, 201]:
        st.sidebar.error(f"GitHub Write Error: {response.text}")

def generate_short_id():
    return f"VJ-{random.randint(1000, 9999)}"

# --- ENHANCED EMAIL ENGINE ---
def send_mail(to_email, subject, body, cc_emails=""):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    if cc_emails:
        msg['Cc'] = cc_emails

    try:
        with smtplib.SMTP_SSL(ZOHO_SMTP, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PWD)
            server.send_message(msg)
        return True, "Email sent successfully."
    except Exception as e:
        return False, f"⚠️ Mail Error: {str(e)}"

# --- UI SETUP & CSS ---
st.markdown(f"""
    <style>
        .ei-header-banner {{ position: fixed; top: 0; left: 0; width: 100%; height: 8px; background-color: {COLOR_BRAND}; z-index: 999999; }}
        .ei-footer-banner {{ position: fixed; bottom: 0; left: 0; width: 100%; background-color: {COLOR_BRAND}; color: #FFFFFF; text-align: center; padding: 12px 0; z-index: 999999; font-family: sans-serif; font-size: 14px; box-shadow: 0 -2px 10px rgba(0,0,0,0.1); letter-spacing: 0.5px; }}
        .main .block-container {{ padding-bottom: 90px !important; padding-top: 35px !important; }}
        div.stButton > button:first-child {{ border-radius: 6px; border: 1px solid {COLOR_BRAND}; color: {COLOR_BRAND}; transition: all 0.3s; }}
        div.stButton > button:first-child:hover {{ background-color: {COLOR_BRAND}; color: white; }}
    </style>
    <div class="ei-header-banner"></div>
    <div class="ei-footer-banner">
        <strong>Ei</strong> | VJ Applications & Impact Dashboards &copy; {datetime.now().year}
    </div>
""", unsafe_allow_html=True)

if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency-systems-regular/96/0284c7/dashboard-layout.png", width=50)
    st.title("Workspace Nav")
    page = st.radio("Go to:", ["Submit Request", "App & Dashboard Directory", "Admin Portal"])
    st.divider()
    if st.session_state.admin_auth:
        if st.button("Logout Admin", use_container_width=True):
            st.session_state.admin_auth = False
            st.rerun()

# ==========================================
# PAGE 1: SUBMIT REQUEST
# ==========================================
if page == "Submit Request":
    st.header("📩 Request Support or New Dashboard")
    st.caption("Please provide detailed requirements to help us prioritize and build your solution faster.")
    
    with st.form("ticket_form", clear_on_submit=True):
        st.subheader("1. Requester Details")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Your Name*")
            email = st.text_input("Your Work Email*")
        
        st.subheader("2. Request Context")
        col3, col4 = st.columns(2)
        with col3:
            req_type = st.selectbox("Type of Support Needed*", ["New Dashboard Creation", "Existing Dashboard Modification", "Data Extraction / SQL Help", "Bug / Error Resolution", "Consultation / Architecture"])
            urgency = st.selectbox("Initial Priority*", ["Low", "Medium", "High", "Critical"])
        with col4:
            url = st.text_input("Reference Data/Application URL (If any)")
        
        st.subheader("3. Technical Details")
        requirements = st.text_area("Specific Requirements*", placeholder="e.g., Need a bar chart showing student performance...", height=100)
        desc = st.text_area("Detailed Description / Use Case*", placeholder="Explain the context. Why is this needed?", height=100)
        
        if st.form_submit_button("Submit Request", use_container_width=True):
            if name and "@" in email and requirements and desc:
                t_id = generate_short_id()
                p_map = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}
                
                # Fetch live data from GitHub, append, and save
                tickets = load_data(TICKET_JSON)
                
                ticket = {
                    "id": t_id, "name": name, "email": email, "type": req_type, 
                    "priority": p_map[urgency], "priority_str": urgency, "url": url, 
                    "requirements": requirements, "description": desc, 
                    "status": "Open", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                
                tickets.append(ticket)
                with st.spinner("Saving to GitHub..."):
                    save_data(tickets, TICKET_JSON) 
                
                user_mail_content = f"Hi {name},\n\nYour request {t_id} ({req_type}) has been successfully logged. \n\nWe will review your requirements shortly and keep you updated."
                send_mail(email, f"Ticket Logged: {t_id}", user_mail_content)
                
                admin_alert_content = f"🚨 NEW TICKET RECEIVED 🚨\n\nID: {t_id}\nFrom: {name} ({email})\nPriority: {urgency}\nType: {req_type}\n\nRequirements:\n{requirements}\n\nDescription:\n{desc}"
                send_mail(SENDER_EMAIL, f"New Ticket Alert: {t_id} - {urgency}", admin_alert_content)
                
                st.success(f"Ticket {t_id} submitted and committed to GitHub! A confirmation email was sent.")
                st.balloons()
            else:
                st.error("Please fill in all mandatory fields (*).")

# ==========================================
# PAGE 2: APP & DASHBOARD DIRECTORY
# ==========================================
elif page == "App & Dashboard Directory":
    st.header("🌟 Existing Apps & Dashboards")
    st.caption("Browse currently live tools and platforms.")
    
    directory = load_data(DIRECTORY_JSON)
    
    if not directory:
        st.info("No projects showcased yet. Check back soon!")
    else:
        all_categories = ["All", "Application", "Dashboard for School", "Internal Dashboard", "Other"]
        selected_cat = st.radio("Filter by Category:", all_categories, horizontal=True)
        st.write("") 
        
        filtered_directory = directory if selected_cat == "All" else [item for item in directory if item.get('type') == selected_cat]
        
        if not filtered_directory:
            st.warning(f"No items found in the '{selected_cat}' category.")
        else:
            cols = st.columns(2)
            for idx, item in enumerate(filtered_directory):
                with cols[idx % 2]:
                    with st.container(border=True):
                        st.subheader(item.get('title', 'Untitled'))
                        st.caption(f"Category: {item.get('type', 'Uncategorized')}")
                        st.write(item.get('description', ''))
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            if item.get('url'): st.link_button("View Live", item['url'], use_container_width=True)
                        with c2:
                            with st.popover("How to Use", use_container_width=True): 
                                st.markdown(f"**Instructions:**\n\n{item.get('usage', 'No instructions provided.')}")

# ==========================================
# PAGE 3: ADMIN PORTAL
# ==========================================
else:
    if not st.session_state.admin_auth:
        st.subheader("Admin Access")
        pw = st.text_input("Enter Workspace Password", type="password")
        if st.button("Secure Login"):
            if pw == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("Access Denied. Incorrect Password.")
    else:
        tab_tickets, tab_leader, tab_port = st.tabs(["🎫 Manage Tickets", "📊 Leaderboard & Details", "🌟 Manage Directory"])
        
        tickets = load_data(TICKET_JSON)
        
        # --- TAB 1: TICKETS ---
        with tab_tickets:
            if tickets:
                df = pd.DataFrame(tickets)
                color_map = {1: "🔴 1-Critical", 2: "🟠 2-High", 3: "🟡 3-Medium", 4: "🟢 4-Low", "1": "🔴 1-Critical", "2": "🟠 2-High", "3": "🟡 3-Medium", "4": "🟢 4-Low"}
                
                df['priority'] = df['priority'].astype(str)
                df['Priority Level'] = df['priority'].map(color_map)
                
                selected_priorities = st.multiselect("Filter by Priority:", options=["🔴 1-Critical", "🟠 2-High", "🟡 3-Medium", "🟢 4-Low"], default=["🔴 1-Critical", "🟠 2-High", "🟡 3-Medium", "🟢 4-Low"])
                df_filtered = df[df['Priority Level'].isin(selected_priorities)].sort_values("priority")
                view_cols = ["id", "Priority Level", "status", "type", "name", "timestamp"]
                
                active_tab, closed_tab = st.tabs(["🟢 Active Queue", "🔘 Closed / Archive"])
                
                with active_tab:
                    df_active = df_filtered[~df_filtered['status'].isin(['Closed', 'Resolved'])]
                    if not df_active.empty: st.dataframe(df_active[view_cols], use_container_width=True, hide_index=True)
                    else: st.info("No active tickets match the current filter.")
                        
                with closed_tab:
                    df_closed = df_filtered[df_filtered['status'].isin(['Closed', 'Resolved'])]
                    if not df_closed.empty: st.dataframe(df_closed[view_cols], use_container_width=True, hide_index=True)
                    else: st.info("No closed tickets match the current filter.")

                st.divider()
                st.subheader("Update / Triage Ticket")
                active_tickets = [t for t in tickets if t.get('status') not in ['Closed', 'Resolved']]
                
                if active_tickets:
                    tid = st.selectbox("Select Ticket ID to Triage", [t['id'] for t in active_tickets])
                    current_t = next(t for t in tickets if t['id'] == tid)
                    
                    with st.expander(f"Review Details for {tid} ({current_t.get('name', 'Unknown')})"):
                        st.write(f"**Requirements:** {current_t.get('requirements', 'N/A')}")
                        st.write(f"**Description:** {current_t.get('description', 'N/A')}")
                        if current_t.get('url'): st.write(f"**URL:** {current_t['url']}")
                    
                    col_u1, col_u2 = st.columns(2)
                    with col_u1:
                        new_p = st.number_input("Adjust Priority (1=Critical, 4=Low)", 1, 4, value=int(current_t.get('priority', 4)))
                    with col_u2:
                        current_status = current_t.get('status', 'Open')
                        if current_status == 'Resolved': current_status = 'Closed' 
                        status_options = ["Open", "In Progress", "De-prioritized", "Closed"]
                        safe_index = status_options.index(current_status) if current_status in status_options else 0
                        new_s = st.selectbox("Update Status", status_options, index=safe_index)
                    
                    st.write("**Communication Options:**")
                    admin_comments = st.text_area("Admin Comments (This will be included in the email to the user)")
                    cc_recipients = st.text_input("CC Recipients (Comma-separated emails)")
                    deprio_reason = st.text_area("Reason for De-prioritization*") if new_s == "De-prioritized" else ""
                    
                    if st.button("Update Ticket & Send Notifications", use_container_width=True):
                        if new_s == "De-prioritized" and not deprio_reason:
                            st.error("You must provide a reason to de-prioritize.")
                        else:
                            old_s = current_t.get('status', 'Open')
                            user_email = current_t.get('email', '')
                            requester_name = current_t.get('name', 'User')
                            comment_block = f"\n\n**Admin Notes:**\n{admin_comments}" if admin_comments else ""
                            
                            # Update DB logic
                            for t in tickets:
                                if t['id'] == tid:
                                    t['status'], t['priority'] = new_s, new_p
                                    
                            with st.spinner("Committing changes to GitHub..."):
                                save_data(tickets, TICKET_JSON)
                            
                            # Notifications
                            if user_email:
                                if old_s != "In Progress" and new_s == "In Progress":
                                    send_mail(user_email, f"Work Started: {tid}", f"Hi {requester_name},\n\nI've officially started working on request {tid}. Expect updates soon!{comment_block}", cc_recipients)
                                elif new_s == "De-prioritized" and old_s != "De-prioritized":
                                    send_mail(user_email, f"Status Update: {tid}", f"Hi {requester_name},\n\nRegarding request {tid}:\n\nThis task has been temporarily de-prioritized.\nReason: {deprio_reason}{comment_block}", cc_recipients)
                                elif new_s == "Closed" and old_s not in ["Closed", "Resolved"]:
                                    send_mail(user_email, f"Resolved & Closed: {tid}", f"Hi {requester_name},\n\nYour request {tid} has been officially resolved and closed!{comment_block}", cc_recipients)
                                elif admin_comments:
                                    send_mail(user_email, f"Ticket Update: {tid}", f"Hi {requester_name},\n\nAn update has been added to your request {tid}:{comment_block}", cc_recipients)

                            st.success(f"Ticket {tid} successfully updated and saved to GitHub! Notifications sent.")
                            st.rerun()
            else:
                st.info("Your queue is entirely empty.")

        # --- TAB 2: ENHANCED LEADERBOARD & TICKET DETAILS ---
        with tab_leader:
            st.subheader("🏆 Top Requesters & Ticket Breakdowns")
            st.caption("Expand a requester's name to view all their submitted tickets.")
            
            if tickets:
                df = pd.DataFrame(tickets)
                if 'name' in df.columns:
                    leaderboard = df.groupby('name').agg(
                        Tickets_Submitted=('id', 'count'),
                        Active_Tickets=('status', lambda x: sum(~x.isin(['Closed', 'Resolved'])))
                    ).reset_index().sort_values(by='Tickets_Submitted', ascending=False)
                    
                    st.dataframe(leaderboard, hide_index=True, use_container_width=True)
                    
                    st.divider()
                    st.markdown("### 📋 Detailed Ticket View by Requester")
                    
                    for _, row in leaderboard.iterrows():
                        user_name = row['name']
                        with st.expander(f"👤 {user_name} ({row['Tickets_Submitted']} Total Tickets)"):
                            user_tickets = df[df['name'] == user_name][['id', 'priority_str', 'status', 'type', 'timestamp']]
                            user_tickets.columns = ['Ticket ID', 'Priority', 'Status', 'Request Type', 'Submitted On']
                            st.dataframe(user_tickets, hide_index=True, use_container_width=True)
            else:
                st.info("No tickets to analyze yet.")

        # --- TAB 3: MANAGE DIRECTORY ---
        with tab_port:
            st.subheader("Manage App & Dashboard Directory")
            dir_action = st.radio("Choose Action:", ["Publish New Application", "Edit / Delete Existing"], horizontal=True)
            
            directory = load_data(DIRECTORY_JSON)
            
            if dir_action == "Publish New Application":
                with st.form("directory_form", clear_on_submit=True):
                    p_title = st.text_input("Name*")
                    p_type = st.selectbox("Category", ["Application", "Dashboard for School", "Internal Dashboard", "Other"])
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
                            categories = ["Application", "Dashboard for School", "Internal Dashboard", "Other"]
                            curr_cat = curr_app.get('type', 'Other')
                            cat_index = categories.index(curr_cat) if curr_cat in categories else 3
                            
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