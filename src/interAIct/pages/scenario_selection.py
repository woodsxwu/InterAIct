import streamlit as st
from database.scenario_dao import ScenarioDAO

def show_scenario_selection():
    """Display a page for selecting which scenario to play"""
    st.markdown("<h1 style='text-align: center;'>Choose a Scenario</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; font-size: 20px;'>Pick a social situation to practice!</p>",
        unsafe_allow_html=True
    )

    # Get all available scenarios
    try:
        scenarios = ScenarioDAO.get_all_scenarios()
    except Exception as e:
        st.error(f"Failed to load scenarios: {e}")
        scenarios = []

    # Display scenarios in a grid or list
    if scenarios:
        # Create two columns for scenarios
        col1, col2 = st.columns(2)

        # Distribute scenarios between columns
        for i, scenario in enumerate(scenarios):
            col = col1 if i % 2 == 0 else col2

            with col:
                with st.container():
                    # Create a card-like container for each scenario
                    st.markdown(f"""
                    <div style="border: 2px solid {st.session_state.selected_avatar['color']}; 
                                border-radius: 15px; 
                                padding: 15px; 
                                margin-bottom: 20px;
                                background-color: {st.session_state.selected_avatar['color']}10;">
                        <h3>{scenario['title']}</h3>
                        <p>{scenario['description']}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Show scenario image with reduced size
                    st.image(scenario['image_path'], width=250)

                    # Add button to start this scenario
                    if st.button(f"Play this scenario", key=f"scenario_{scenario['id']}", use_container_width=True):
                        # Directly set the video path to the fixed location
                        st.session_state.selected_video = "src/ineractAI/videos/scenario_1_phase_entering.mp4"

                        if 'current_phase' in st.session_state:
                            del st.session_state.current_phase  # Reset phase tracking

                        st.session_state.page = 'scenario'
                        st.rerun()

    else:
        st.warning("No scenarios found. Please contact the administrator.")

    # Back button
    if st.button("Back to Home", use_container_width=True):
        st.session_state.page = 'avatar_selection'
        st.rerun()
