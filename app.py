import streamlit as st
import qrcode
from io import BytesIO
import pandas as pd
from datetime import datetime
import os
from streamlit_js_eval import streamlit_js_eval
from streamlit_geolocation import streamlit_geolocation
from utils_db import (
    sign_up_lecturer, sign_in_lecturer, 
    create_class, get_classes_by_lecturer, get_class_details, update_attendees
)
import math

# Page Config
st.set_page_config(page_title="TrackAS - Firestore Attendance", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for Premium Look
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #000D46;
        color: white;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #001a8c;
        border: none;
    }
    .card {
        padding: 20px;
        border-radius: 15px;
        background: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .title-text {
        color: #000D46;
        font-weight: bold;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# Session State Initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_details" not in st.session_state:
    st.session_state.user_details = None

# Helper Functions
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def generate_qr(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf)
    return buf.getvalue()

# URL Query Params
query_params = st.query_params

# Navigation Routing
if "courseId" in query_params:
    # Student Attendance Page
    course_id = query_params["courseId"]
    target_lat = float(query_params.get("lat", 0))
    target_lng = float(query_params.get("lng", 0))
    
    st.markdown("<h1 class='title-text'>Student Attendance</h1>", unsafe_allow_html=True)
    
    class_info = get_class_details(course_id)
    if class_info:
        st.info(f"📍 Class: {class_info['course_title']} ({class_info['course_code']})")
        st.write(f"🏢 Venue: {class_info['location_name']}")
        
        # Get Location using the dedicated streamlit-geolocation component
        st.write("🔍 Click below to verify your location:")
        location_data = streamlit_geolocation()
        
        # Extract lat/lng from the component's output
        loc = None
        if location_data and location_data.get("latitude") is not None:
            loc = {"lat": location_data["latitude"], "lng": location_data["longitude"]}

        if loc:
            dist = haversine(loc['lat'], loc['lng'], target_lat, target_lng)
            st.write(f"📏 Your distance to venue: {dist:.2f} meters")
            
            if dist <= 500:
                with st.form("attendance_form"):
                    name = st.text_input("Full Name")
                    matric = st.text_input("Matric Number")
                    submit = st.form_submit_button("Mark Attendance")
                    
                    if submit:
                        if name and matric:
                            current_attendees = class_info.get("attendees", [])
                            if any(a['matric_no'] == matric.upper() for a in current_attendees):
                                st.warning("You have already marked attendance!")
                            else:
                                new_attendee = {
                                    "name": name.upper(),
                                    "matric_no": matric.upper(),
                                    "timestamp": datetime.now().isoformat()
                                }
                                current_attendees.append(new_attendee)
                                update_attendees(course_id, current_attendees)
                                st.success("Attendance marked successfully!")
                                st.balloons()
                        else:
                            st.error("Please fill all fields")
            else:
                st.error("❌ You are too far from the venue to mark attendance. (Radius: 500m)")
        else:
            st.warning("Waiting for location access... Please enable GPS.")
    else:
        st.error("Invalid Attendance Link")

elif not st.session_state.authenticated:
    # Auth Page
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.markdown("<h2 class='title-text'>Lecturer Login</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                try:
                    user_data = sign_in_lecturer(email, password)
                    if user_data:
                        st.session_state.authenticated = True
                        st.session_state.user_details = user_data
                        st.rerun()
                    else:
                        st.error("Invalid email or password")
                except Exception as e:
                    st.error(f"Login Failed: {str(e)}")
                    
    with tab2:
        st.markdown("<h2 class='title-text'>Create Account</h2>", unsafe_allow_html=True)
        with st.form("reg_form"):
            name = st.text_input("Full Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone Number")
            password = st.text_input("Password", type="password")
            confirm = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Register"):
                if password == confirm:
                    try:
                        user = sign_up_lecturer(email, password, name, phone)
                        if user:
                            st.success("Account created! You can now login.")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                else:
                    st.error("Passwords do not match")

else:
    # Dashboard
    st.sidebar.title(f"TrackAS")
    st.sidebar.write(f"Logged in as: {st.session_state.user_details['fullName']}")
    choice = st.sidebar.radio("Navigation", ["Dashboard", "Create Class", "Attendance History", "Logout"])
    
    # Use email as lecturer_id for Firestore queries
    lecturer_email = st.session_state.user_details['email']

    if choice == "Dashboard":
        st.markdown("<h1 class='title-text'>Lecturer Dashboard</h1>", unsafe_allow_html=True)
        classes = get_classes_by_lecturer(lecturer_email)
        if classes:
            st.write(f"Total Classes: {len(classes)}")
            # Show summary cards
            col1, col2 = st.columns(2)
            col1.metric("Classes Scheduled", len(classes))
            total_attendees = sum(len(c.get('attendees', [])) for c in classes)
            col2.metric("Total Attendance Records", total_attendees)
        else:
            st.info("No classes scheduled yet.")

    elif choice == "Create Class":
        st.markdown("<h1 class='title-text'>Schedule New Class</h1>", unsafe_allow_html=True)
        with st.form("class_form"):
            title = st.text_input("Course Title")
            code = st.text_input("Course Code")
            venue = st.text_input("Venue Name")
            date = st.date_input("Date")
            time = st.time_input("Time")
            note = st.text_area("Note (Optional)")
            
            st.write("📍 Select Venue Coordinates")
            lat = st.number_input("Latitude", value=6.5244, format="%.6f")
            lng = st.number_input("Longitude", value=3.3792, format="%.6f")
            
            if st.form_submit_button("Generate QR & Schedule"):
                class_data = {
                    "course_title": title,
                    "course_code": code,
                    "location_name": venue,
                    "date": date.isoformat(),
                    "time": f"{date.isoformat()}T{time.isoformat()}",
                    "note": note,
                    "lecturer_id": lecturer_email,
                    "lat": lat,
                    "lng": lng
                }
                res = create_class(class_data)
                if res:
                    st.success("Class Scheduled!")
                    # Show QR
                    base_url = os.getenv("VITE_VERCEL_URL", "http://localhost:8501")
                    qr_link = f"{base_url}?courseId={res[0]['course_id']}&lat={lat}&lng={lng}"
                    qr_img = generate_qr(qr_link)
                    st.image(qr_img, caption="Scan this for attendance")
                    st.code(qr_link, language="markdown")

    elif choice == "Attendance History":
        st.markdown("<h1 class='title-text'>Attendance History</h1>", unsafe_allow_html=True)
        classes = get_classes_by_lecturer(lecturer_email)
        if classes:
            df_classes = pd.DataFrame(classes)
            # Reorder columns for display
            display_cols = ['course_code', 'course_title', 'location_name', 'date']
            st.dataframe(df_classes[display_cols])
            
            selected_class_id = st.selectbox("Select Class to view Attendance", df_classes['course_id'])
            if selected_class_id:
                sel_class = next(c for c in classes if c['course_id'] == selected_class_id)
                attendees = sel_class.get('attendees', [])
                if attendees:
                    st.write(f"### Attendees for {sel_class['course_code']}")
                    st.table(pd.DataFrame(attendees))
                    # Export
                    csv = pd.DataFrame(attendees).to_csv(index=False)
                    st.download_button("Download CSV", csv, file_name=f"attendance_{sel_class['course_code']}.csv", mime="text/csv")
                else:
                    st.warning("No attendees yet.")
        else:
            st.info("No classes found.")

    elif choice == "Logout":
        st.session_state.authenticated = False
        st.session_state.user_details = None
        st.rerun()
