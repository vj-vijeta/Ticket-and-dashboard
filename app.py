import streamlit as st
import pandas as pd
import json
import os
import smtplib
import random
from datetime import datetime
from email.message import EmailMessage

# --- CONFIGURATION ---
TICKET_JSON = "tickets_db.json"
DIRECTORY_JSON = "directory_db.json"
ADMIN_PASSWORD = "Vijeta@17"
SENDER_EMAIL = "vijeta@ei.study"
SENDER_PWD = "heJWieEXqymE"  
ZOHO_SMTP = "smtp.zoho.in"   

# Calm Brand Styling
COLOR_BRAND = "#0284c7"  

# --- DATA HELPERS ---
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f: return json.load(f)
    return []

def save_json(data, file_path):
    with open(file_path, "w") as f: json.dump(data, f, indent=4)

def generate_short_id():
    return f"VJ-{random.randint(1000, 9999)}"

# --- EMAIL ENGINE ---
def send_mail(to_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL(ZOHO_SMTP, 465) as server:
            server.login(SENDER_EMAIL, SENDER_PWD)
            server.send_message(msg)
        return True, "Email sent successfully."
    except Exception as e:
        return False, f"⚠️ Mail Error: {str(e)}"

# --- UI SETUP & CSS ---
st.set_page_config(page_title="Ei | VJ Workspace", page_icon="🌊", layout="wide")

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

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency-systems-regular/96/0284c7/dashboard-layout.png", width=50)
    st.title("Workspace Nav")
    page = st.radio("Go to:", ["Submit Request", "App & Dashboard Directory", "Admin Portal"])
    st.divider()
    if st.session_state.admin_auth:
        if st.button("Logout Admin", use_container_width=True):
            st.session_state.admin_auth = False
            st.rerun()

# --- PAGE 1: SUBMIT REQUEST ---
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
                ticket = {
                    "id": t_id, "name": name, "email": email, "type": req_type, 
                    "priority": p_map[urgency], "priority_str": urgency, "url": url, 
                    "requirements": requirements, "description": desc, 
                    "status": "Open", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                
                tickets = load_json(TICKET_JSON)
                tickets.append(ticket)
                save_json(tickets, TICKET_JSON)
                
                mail_content = f"Hi {name},\n\nYour request {t_id} ({req_type}) has been successfully logged. \n\n--- TICKET DETAILS ---\nPriority: {urgency}\nReference URL: {url if url else 'None Provided'}\n\nREQUIREMENTS:\n{requirements}\n\nDESCRIPTION:\n{desc}\n----------------------\n\nWe will review your requirements shortly and keep you updated."
                
                success, msg = send_mail(email, f"Ticket Logged: {t_id}", mail_content)
                if success:
                    st.success(f"Ticket {t_id} submitted! A detailed confirmation email was sent.")
                    st.balloons()
                else:
                    st.warning(f"Ticket logged locally, but email failed to send: {msg}")
            else:
                st.error("Please fill in all mandatory fields (*).")

# --- PAGE 2: APP & DASHBOARD DIRECTORY ---
elif page == "App & Dashboard Directory":
    st.header("🌟 Existing Apps & Dashboards")
    st.caption("Browse currently live tools and platforms.")
    
    directory = load_json(DIRECTORY_JSON)
    if not directory:
        st.info("No projects showcased yet. Check back soon!")
    else:
        # Build the Filter UI
        all_categories = ["All", "Application", "Dashboard for School", "Internal Dashboard", "Other"]
        selected_cat = st.radio("Filter by Category:", all_categories, horizontal=True)
        st.write("") 
        
        # Apply Filter
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

# --- PAGE 3: ADMIN PORTAL ---
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
        tab_tickets, tab_leader, tab_port = st.tabs(["🎫 Manage Tickets", "📊 Leaderboard", "🌟 Manage Directory"])
        tickets = load_json(TICKET_JSON)
        
        # --- TAB 1: TICKETS ---
        with tab_tickets:
            if tickets:
                df = pd.DataFrame(tickets)
                color_map = {1: "🔴 1-Critical", 2: "🟠 2-High", 3: "🟡 3-Medium", 4: "🟢 4-Low"}
                df['Priority Level'] = df['priority'].map(color_map)
                
                selected_priorities = st.multiselect("Filter by Priority:", options=["🔴 1-Critical", "🟠 2-High", "🟡 3-Medium", "🟢 4-Low"], default=["🔴 1-Critical", "🟠 2-High", "🟡 3-Medium", "🟢 4-Low"])
                df_filtered = df[df['Priority Level'].isin(selected_priorities)].sort_values("priority")
                view_cols = ["id", "Priority Level", "status", "type", "name", "timestamp"]
                
                active_tab, closed_tab = st.tabs(["🟢 Active Queue", "🔘 Closed / Archive"])
                
                with active_tab:
                    df_active = df_filtered[~df_filtered['status'].isin(['Resolved', 'Closed'])]
                    if not df_active.empty: st.dataframe(df_active[view_cols], use_container_width=True, hide_index=True)
                    else: st.info("No active tickets match the current filter.")
                        
                with closed_tab:
                    df_closed = df_filtered[df_filtered['status'].isin(['Resolved', 'Closed'])]
                    if not df_closed.empty: st.dataframe(df_closed[view_cols], use_container_width=True, hide_index=True)
                    else: st.info("No closed tickets match the current filter.")

                st.divider()
                st.subheader("Update / Triage Ticket")
                active_tickets = [t for t in tickets if t['status'] not in ['Resolved', 'Closed']]
                
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
                        new_s = st.selectbox("Update Status", ["Open", "In Progress", "De-prioritized", "Resolved"], index=["Open", "In Progress", "De-prioritized", "Resolved"].index(current_t.get('status', 'Open')))
                    
                    deprio_reason = st.text_area("Reason for De-prioritization*") if new_s == "De-prioritized" else ""
                    
                    if st.button("Apply Status & Notify User"):
                        if new_s == "De-prioritized" and not deprio_reason:
                            st.error("You must provide a reason to de-prioritize.")
                        else:
                            old_s = current_t.get('status', 'Open')
                            user_email = current_t.get('email', '')
                            if user_email:
                                if old_s != "In Progress" and new_s == "In Progress":
                                    send_mail(user_email, f"Work Started: {tid}", f"Hi {current_t.get('name', 'User')},\n\nI've started working on request {tid}. Expect updates soon!")
                                elif new_s == "De-prioritized" and old_s != "De-prioritized":
                                    send_mail(user_email, f"Status Update: {tid}", f"Hi {current_t.get('name', 'User')},\n\nRegarding request {tid}:\n\nThis task has been temporarily de-prioritized.\nReason: {deprio_reason}\n\nWe will revisit this shortly.")
                                elif new_s == "Resolved" and old_s != "Resolved":
                                    send_mail(user_email, f"Resolved: {tid}", f"Hi {current_t.get('name', 'User')},\n\nYour request {tid} has been officially resolved and closed!")
                            
                            for t in tickets:
                                if t['id'] == tid:
                                    t['status'], t['priority'] = new_s, new_p
                            save_json(tickets, TICKET_JSON)
                            st.success(f"Ticket {tid} successfully updated!")
                            st.rerun()
            else:
                st.info("Your queue is entirely empty.")

        # --- TAB 2: LEADERBOARD ---
        with tab_leader:
            st.subheader("🏆 Top Requesters")
            if tickets:
                df = pd.DataFrame(tickets)
                if 'name' in df.columns:
                    leaderboard = df['name'].value_counts().reset_index()
                    leaderboard.columns = ['Requester Name', 'Tickets Submitted']
                    c1, c2 = st.columns([1, 2])
                    with c1: st.dataframe(leaderboard, hide_index=True)
                    with c2: st.bar_chart(leaderboard.set_index('Requester Name'), color=COLOR_BRAND)

        # --- TAB 3: MANAGE DIRECTORY ---
        with tab_port:
            st.subheader("Manage App & Dashboard Directory")
            dir_action = st.radio("Choose Action:", ["Publish New Application", "Edit / Delete Existing"], horizontal=True)
            directory = load_json(DIRECTORY_JSON)
            
            # SUB-ACTION 1: ADD NEW
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
                            save_json(directory, DIRECTORY_JSON)
                            st.success("Successfully added to your public directory!")
                        else:
                            st.error("Name and Description are required.")
                            
            # SUB-ACTION 2: EDIT/DELETE EXISTING
            elif dir_action == "Edit / Delete Existing":
                if not directory:
                    st.info("The directory is currently empty.")
                else:
                    app_names = [app.get('title', 'Untitled') for app in directory]
                    selected_app = st.selectbox("Select Application to Edit", app_names)
                    
                    # Find the specific item index
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
                                    save_json(directory, DIRECTORY_JSON)
                                    st.success(f"Updated '{e_title}' successfully!")
                                    st.rerun()
                                else:
                                    st.error("Name and Description are required.")
                            
                            if delete_btn:
                                directory.pop(app_idx)
                                save_json(directory, DIRECTORY_JSON)
                                st.success(f"Deleted '{selected_app}' from the directory.")
                                st.rerun()