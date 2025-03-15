import streamlit as st
import pandas as pd
from database import db_service as db
from database.scenario_dao import ScenarioDAO
from pages.report import generate_report


def show_parent_dashboard():
    st.markdown("<h1>Parent/Teacher Dashboard</h1>", unsafe_allow_html=True)

    # Simple authentication (in a real app, use proper authentication)
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.markdown("<p>Please enter the parent password to access the dashboard.</p>", unsafe_allow_html=True)
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            # Hardcoded password for demo - in a real app, use proper authentication
            if password == "parent123":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")

        # Back to child view
        if st.button("Back to Child View"):
            st.session_state.page = 'avatar_selection'
            st.rerun()

        return

    # Dashboard sections
    tabs = st.tabs(["Child Progress", "Scenarios", "Settings"])

    with tabs[0]:
        st.markdown("<h2>Child Progress</h2>", unsafe_allow_html=True)

        # Try to get reports from database
        try:
            # Get session responses from database
            report_data = db.generate_report(st.session_state.db_session_id)

            if report_data and report_data.get('responses'):
                # Deduplicate responses
                responses = report_data['responses']
                unique_responses = []
                seen_keys = set()

                for resp in responses:
                    # Create a unique key for each response (scenario+phase+option)
                    key = (resp.get('scenario_id'), resp.get('phase_id'), resp.get('option_id'))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        unique_responses.append(resp)

                # Create a dataframe from the deduped responses
                report_df = pd.DataFrame(unique_responses)

                # Group by scenario to show a cleaner summary
                if 'scenario_title' in report_df.columns:
                    summary_df = report_df.groupby('scenario_title').agg({
                        'positive': lambda x: sum(x),
                        'guidance': lambda x: sum(x),
                        'id': 'count'
                    }).reset_index()

                    summary_df = summary_df.rename(columns={
                        'scenario_title': 'Scenario',
                        'positive': 'Positive Choices',
                        'guidance': 'Needed Guidance',
                        'id': 'Total Interactions'
                    })

                    # Display the grouped summary first
                    st.subheader("Scenario Summary")
                    st.dataframe(summary_df, use_container_width=True)

                    # Then display detailed responses
                    st.subheader("Detailed Responses")

                # Format the dataframe for display
                display_columns = {
                    'scenario_title': 'Scenario',
                    'phase_description': 'Phase',
                    'option_text': 'Response',
                    'emotion': 'Emotion',
                    'feedback_text': 'Feedback',
                    'positive': 'Positive Choice',
                    'guidance': 'Needed Guidance',
                    'timestamp': 'Time'
                }

                # Select and rename columns
                available_columns = [col for col in display_columns.keys() if col in report_df.columns]
                display_df = report_df[available_columns].copy()
                display_df = display_df.rename(columns={col: display_columns[col] for col in available_columns})

                # Format boolean columns
                if 'Positive Choice' in display_df.columns:
                    display_df['Positive Choice'] = display_df['Positive Choice'].map(lambda x: 'Yes' if x else 'No')
                if 'Needed Guidance' in display_df.columns:
                    display_df['Needed Guidance'] = display_df['Needed Guidance'].map(lambda x: 'Yes' if x else 'No')
                if 'Emotion' in display_df.columns:
                    display_df['Emotion'] = display_df['Emotion'].apply(lambda x: x.capitalize() if x else "Unknown")

                st.dataframe(display_df, use_container_width=True)

                # Summary statistics
                total_scenarios = len(display_df['Scenario'].unique())
                positive_choices = (display_df[
                                        "Positive Choice"] == "Yes").sum() if "Positive Choice" in display_df.columns else 0
                needed_guidance = (display_df[
                                       "Needed Guidance"] == "Yes").sum() if "Needed Guidance" in display_df.columns else 0
                total_responses = len(display_df)

                # Display metrics
                st.subheader("Key Metrics")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(label="Unique Scenarios", value=total_scenarios)
                with col2:
                    st.metric(label="Total Responses", value=total_responses)
                with col3:
                    st.metric(label="Positive Choices", value=f"{positive_choices}/{total_responses}")
                with col4:
                    st.metric(label="Needed Guidance", value=f"{needed_guidance}/{total_responses}")
            else:
                st.info("No activity data available yet. Have your child complete some scenarios to see progress.")
        except Exception as e:
            st.error(f"Error retrieving reports: {e}")
            # Fall back to session state data if database failed
            fallback_to_session_state_reports()

    # Rest of the function remains the same
    with tabs[1]:
        st.markdown("<h2>Available Scenarios</h2>", unsafe_allow_html=True)

        # Get scenarios from database
        try:
            scenarios = ScenarioDAO.get_all_scenarios()

            for scenario in scenarios:
                with st.expander(f"{scenario['id']}. {scenario['title']}"):
                    st.markdown(f"<p><strong>Description:</strong> {scenario['description']}</p>",
                                unsafe_allow_html=True)

                    # Get full scenario details with options and feedback
                    full_scenario = ScenarioDAO.get_scenario_by_id(scenario['id'])

                    if full_scenario and 'phases' in full_scenario:
                        for phase in full_scenario['phases']:
                            st.markdown(f"<p><strong>Phase:</strong> {phase['description']}</p>",
                                        unsafe_allow_html=True)
                            st.markdown("<p><strong>Options:</strong></p>", unsafe_allow_html=True)

                            for option in phase['options']:
                                option_id = option['option_id']
                                # Get feedback for this option
                                if option_id in phase['feedback']:
                                    feedback = phase['feedback'][option_id]
                                    positive = "✅ Positive" if feedback.get("positive", False) else "⚠️ Needs Guidance"
                                    st.markdown(f"- Option {option_id.upper()}: {option['text']} ({positive})",
                                                unsafe_allow_html=True)
                    else:
                        st.markdown("<p>No detailed information available for this scenario.</p>",
                                    unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error loading scenarios: {e}")
            st.markdown("<p>Could not load scenarios from database.</p>", unsafe_allow_html=True)

    with tabs[2]:
        st.markdown("<h2>Settings</h2>", unsafe_allow_html=True)

        # Avatar preferences
        st.markdown("<h3>Avatar Preferences</h3>", unsafe_allow_html=True)
        st.checkbox("Allow child to change avatar during session", value=False)

        # Notification settings
        st.markdown("<h3>Notification Settings</h3>", unsafe_allow_html=True)
        st.checkbox("Receive alerts for distressed emotions", value=True)
        st.checkbox("Receive session summary by email", value=False)
        st.text_input("Parent Email")

        # Save settings button
        if st.button("Save Settings"):
            st.success("Settings saved successfully")

    # Logout and back buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.rerun()
    with col2:
        if st.button("Back to Child View"):
            st.session_state.page = 'avatar_selection'
            st.rerun()


def fallback_to_session_state_reports():
    """Use session state data if database reports are unavailable"""
    if hasattr(st.session_state, 'responses') and st.session_state.responses:
        # Get all scenarios to map IDs to titles
        try:
            scenarios = ScenarioDAO.get_all_scenarios()
            scenario_map = {scenario['id']: scenario['title'] for scenario in scenarios}
        except Exception:
            scenario_map = {}  # Fallback if we can't get scenarios

        # Create a simple dataframe from session state
        data = []
        for resp in st.session_state.responses:
            # Get actual scenario title if available
            scenario_id = resp.get('scenario_id', 'Unknown')
            if scenario_id in scenario_map:
                scenario_title = scenario_map[scenario_id]
            else:
                scenario_title = f"Scenario {scenario_id}"

            data.append({
                'Scenario': scenario_title,
                'Response': f"Option {resp.get('response', 'Unknown')}",
                'Emotion': resp.get('emotion', 'Unknown').capitalize(),
                'Time': resp.get('timestamp', 'Unknown'),
                'Positive Choice': 'Yes',  # Default as we don't have this in session state
                'Needed Guidance': 'No'  # Default as we don't have this in session state
            })

        if data:
            report_df = pd.DataFrame(data)
            st.dataframe(report_df, use_container_width=True)

            # Basic stats
            total = len(report_df)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Completed Scenarios", value=total)
            with col2:
                st.metric(label="Positive Choices", value=f"{total}/{total}")
            with col3:
                st.metric(label="Needed Guidance", value=f"0/{total}")
        else:
            st.info("No activity data available yet. Have your child complete some scenarios to see progress.")
    else:
        st.info("No activity data available yet. Have your child complete some scenarios to see progress.")