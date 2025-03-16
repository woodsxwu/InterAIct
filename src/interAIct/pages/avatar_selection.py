import streamlit as st
from database import db_service as db
from utils.session_manager import select_avatar

def show_avatar_selection():
    """Display the avatar selection page"""
    st.markdown("<h1 style='text-align: center;'>Choose Your Friend!</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; font-size: 20px;'>Pick a friend who will help you learn about feelings and making friends</p>",
        unsafe_allow_html=True)

    # Get avatars from the database instead of direct import
    try:
        avatars = db.get_avatars()
    except Exception as e:
        st.error(f"Failed to load avatars: {e}")
        avatars = []

    # Display avatars in a grid
    if avatars:
        cols = st.columns(len(avatars))
        for i, avatar in enumerate(avatars):
            with cols[i]:
                st.markdown(f"""
                <div class='avatar-btn'>
                    <div style='text-align: center;'>
                        <div class='emoji-large'>{avatar['emoji']}</div>
                        <div style='font-weight: bold;'>{avatar['name']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Choose {avatar['name']}", key=f"avatar_{avatar['id']}", use_container_width=True):
                    select_avatar(avatar)
                    st.session_state.page = 'scenario_selection'
                    st.rerun()
    else:
        st.warning("No avatars found. Please contact the administrator.")