import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import bcrypt
import json
import os

# Initialize Firestore
def get_db():
    if "db" not in st.session_state:
        # 1. Try to load from st.secrets
        try:
            if "firestore" in st.secrets:
                key_dict = json.loads(st.secrets["firestore"]["text_key"])
                creds = service_account.Credentials.from_service_account_info(key_dict)
                st.session_state.db = firestore.Client(credentials=creds, project=key_dict["project_id"])
                return st.session_state.db
        except Exception:
            pass

        # 2. Try to load from local JSON file
        cwd = os.getcwd()
        all_files = os.listdir(".")
        json_files = [f for f in all_files if f.endswith(".json") and ("firebase-adminsdk" in f or "firestore-key" in f)]
        
        if json_files:
            try:
                st.session_state.db = firestore.Client.from_service_account_json(json_files[0])
                return st.session_state.db
            except Exception as e:
                st.error(f"Error loading service account JSON ({json_files[0]}): {e}")
        
        # 3. Last resort: Detailed Error
        st.error(f"No Firestore credentials found.")
        st.write(f"**Debug Info:**")
        st.write(f"- CWD: `{cwd}`")
        st.write(f"- JSON Files found: `{json_files}`")
        st.write(f"- All local files: `{all_files[:10]}`...")
        st.info("Please ensure `.streamlit/secrets.toml` or a service account JSON file exists in the current folder.")
        st.stop()
    return st.session_state.db

# --- Auth Functions ---
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def sign_up_lecturer(email, password, full_name, phone_number):
    db = get_db()
    lecturers_ref = db.collection("lecturers")
    
    # Check if user exists
    doc = lecturers_ref.document(email).get()
    if doc.exists:
        raise Exception("Lecturer with this email already exists.")
    
    hashed = hash_password(password)
    data = {
        "fullName": full_name,
        "email": email,
        "phone_number": phone_number,
        "password": hashed,
        "created_at": firestore.SERVER_TIMESTAMP
    }
    lecturers_ref.document(email).set(data)
    # Get the generated ID or just return the email
    return {"id": email, "email": email}

def sign_in_lecturer(email, password):
    db = get_db()
    doc = db.collection("lecturers").document(email).get()
    if doc.exists:
        user_data = doc.to_dict()
        if check_password(password, user_data["password"]):
            return user_data
    return None

# --- Class Functions ---
def create_class(data):
    db = get_db()
    # Add timestamp
    data["created_at"] = firestore.SERVER_TIMESTAMP
    # Attendees as subcollection or field. Field is easier for MVP.
    data["attendees"] = []
    
    # Generate a random ID for the class
    new_class_ref = db.collection("classes").document()
    data["course_id"] = new_class_ref.id
    new_class_ref.set(data)
    return [data]

def get_classes_by_lecturer(lecturer_id):
    db = get_db()
    # Use the filter keyword as recommended by google-cloud-firestore
    classes = db.collection("classes").where(filter=firestore.FieldFilter("lecturer_id", "==", lecturer_id)).stream()
    return [c.to_dict() for c in classes]

def get_class_details(course_id):
    db = get_db()
    doc = db.collection("classes").document(course_id).get()
    return doc.to_dict() if doc.exists else None

def update_attendees(course_id, attendees):
    db = get_db()
    db.collection("classes").document(course_id).update({"attendees": attendees})
