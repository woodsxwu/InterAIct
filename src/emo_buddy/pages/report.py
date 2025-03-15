import streamlit as st
import pandas as pd
from database import db_service as db
from utils.session_manager import get_session_report, reset_session
from database.scenario_dao import ScenarioDAO  # Add this import


def generate_report(responses):
    """Generate a report DataFrame from response data"""
    if not responses:
        return pd.DataFrame()

    report_data = []

    # Process the responses
    for resp in responses:
        scenario_id = resp.get("scenario_id")
        response_option = resp.get("response") or resp.get("option_id", "")
        emotion = resp.get("emotion", "neutral")
        timestamp = resp.get("timestamp", "")
        phase_id = resp.get("phase_id", "")

        # Try to get more detailed information if available
        scenario_title = resp.get("scenario_title", f"Scenario {scenario_id}")
        phase_desc = resp.get("phase_description", phase_id or "Unknown phase")
        option_text = resp.get("option_text", f"Option {response_option}")
        positive = resp.get("positive", True)  # Default to True
        guidance = resp.get("guidance", False)  # Default to False

        report_data.append({
            "Scenario": scenario_title,
            "Phase": phase_desc,
            "Child's Response": option_text,
            "Detected Emotion": emotion.capitalize() if emotion else "Unknown",
            "Positive Choice": "Yes" if positive else "No",
            "Needed Guidance": "Yes" if guidance else "No",
            "Timestamp": timestamp
        })

    # Ensure each unique response appears only once
    # Use a combination of scenario, phase, and response as a unique identifier
    unique_report_data = []
    seen_responses = set()

    for entry in report_data:
        response_key = (entry["Scenario"], entry["Phase"], entry["Child's Response"])
        if response_key not in seen_responses:
            seen_responses.add(response_key)
            unique_report_data.append(entry)

    return pd.DataFrame(unique_report_data)


def show_report():
    st.markdown("<h1>Social Skills Learning Report</h1>", unsafe_allow_html=True)
    st.markdown("<p>This report provides insights into the child's responses to social scenarios.</p>",
                unsafe_allow_html=True)

    # Try to get the session report from database
    try:
        report_data = get_session_report()
    except Exception:
        report_data = None

    # If database report is available, use it
    if report_data and report_data.get('responses'):
        # Create DataFrame from the report data
        responses = report_data['responses']

        # Deduplicate responses based on scenario_id, phase_id, and option_id
        unique_responses = []
        seen_responses = set()
        for resp in responses:
            response_key = (resp.get('scenario_id'), resp.get('phase_id'), resp.get('option_id'))
            if response_key not in seen_responses:
                seen_responses.add(response_key)
                unique_responses.append(resp)

        if unique_responses:
            report_df = pd.DataFrame(unique_responses)

            # Select and rename relevant columns
            columns_to_display = {
                'scenario_title': 'Scenario',
                'phase_description': 'Phase',
                'option_text': 'Child\'s Response',
                'emotion': 'Detected Emotion',
                'positive': 'Positive Choice',
                'guidance': 'Needed Guidance',
                'timestamp': 'Timestamp'
            }

            # Filter and rename columns
            # Handle missing columns gracefully
            available_columns = [col for col in columns_to_display.keys() if col in report_df.columns]

            if available_columns:
                display_df = report_df[available_columns].copy()
                display_df = display_df.rename(columns={col: columns_to_display[col] for col in available_columns})

                # Format boolean columns if they exist
                if 'positive' in available_columns:
                    display_df['Positive Choice'] = display_df['Positive Choice'].map(lambda x: 'Yes' if x else 'No')
                if 'guidance' in available_columns:
                    display_df['Needed Guidance'] = display_df['Needed Guidance'].map(lambda x: 'Yes' if x else 'No')
                if 'emotion' in available_columns:
                    display_df['Detected Emotion'] = display_df['Detected Emotion'].apply(
                        lambda x: x.capitalize() if x else "Unknown")

                st.dataframe(display_df, use_container_width=True)

                # Summary statistics
                positive_choices = (display_df.get("Positive Choice", pd.Series(["Yes"])) == "Yes").sum()
                needed_guidance = (display_df.get("Needed Guidance", pd.Series(["No"])) == "Yes").sum()
                total_responses = len(display_df)

                # Display metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(label="Total Responses", value=total_responses)
                with col2:
                    st.metric(label="Positive Choices", value=f"{positive_choices}/{total_responses}")
                with col3:
                    st.metric(label="Needed Guidance", value=f"{needed_guidance}/{total_responses}")

                # Show recommendations based on performance
                show_recommendations(positive_choices, needed_guidance, total_responses)
            else:
                st.warning("Response data is missing expected columns. Using simplified report format.")
                alt_df = generate_report(unique_responses)
                st.dataframe(alt_df, use_container_width=True)
                show_recommendations(len(unique_responses), 0, len(unique_responses))
        else:
            st.info("No responses recorded for this session.")
    else:
        # Fall back to session state if database report is not available
        fallback_to_session_state()

    # Buttons for navigation
    col1, col2 = st.columns(2)
    with col1:
        # Start over button
        if st.button("Start Over", key="restart_btn", use_container_width=True):
            reset_session()
            st.rerun()

    with col2:
        # Return to parent dashboard button
        if st.button("Parent Dashboard", key="parent_dashboard_btn", use_container_width=True):
            st.session_state.page = 'parent_dashboard'
            st.rerun()


def fallback_to_session_state():
    """Use session state responses if database report is not available"""
    # Ensure responses exist
    if not hasattr(st.session_state, 'responses') or not st.session_state.responses:
        st.info("No scenarios have been completed yet. Complete some scenarios to see your report.")
        return

    # Get all scenarios to map IDs to titles
    try:
        scenarios = ScenarioDAO.get_all_scenarios()
        scenario_map = {scenario['id']: scenario['title'] for scenario in scenarios}
    except Exception:
        scenario_map = {}  # Fallback if we can't get scenarios

    # Format session state responses and deduplicate
    report_data = []
    seen_responses = set()

    for resp in st.session_state.responses:
        # Create a unique key for each response
        response_key = (
            resp.get('scenario_id', 'Unknown'),
            resp.get('phase_id', 'Unknown'),
            resp.get('response', 'Unknown')
        )

        if response_key not in seen_responses:
            seen_responses.add(response_key)

            # Get actual scenario title if available
            scenario_id = resp.get('scenario_id', 'Unknown')
            if scenario_id in scenario_map:
                scenario_title = scenario_map[scenario_id]
            else:
                scenario_title = f"Scenario {scenario_id}"

            report_data.append({
                "Scenario": scenario_title,
                "Phase": resp.get('phase_id', 'Unknown'),
                "Child's Response": f"Option {resp.get('response', 'Unknown')}",
                "Detected Emotion": resp.get('emotion', 'Unknown').capitalize(),
                "Positive Choice": "Yes",  # Default as we don't have this in session state
                "Needed Guidance": "No",  # Default as we don't have this in session state
                "Timestamp": resp.get('timestamp', 'Unknown')
            })

    if report_data:
        report_df = pd.DataFrame(report_data)
        st.dataframe(report_df, use_container_width=True)

        # Basic stats
        total_responses = len(report_df)
        st.metric(label="Total Responses", value=total_responses)

        # Show generic recommendations
        show_recommendations(total_responses, 0, total_responses)
    else:
        st.info("No scenarios have been completed yet. Complete some scenarios to see your report.")


def show_recommendations(positive_choices, needed_guidance, total_responses):
    """Display personalized recommendations based on the child's performance"""
    st.markdown("<h2>Recommendations for Parents/Teachers</h2>", unsafe_allow_html=True)

    # Generate personalized recommendations based on responses
    if needed_guidance > total_responses / 2:
        st.markdown("""
        <div class="avatar-message">
            <h3>Areas for Growth</h3>
            <p>Your child may benefit from additional practice with social interactions. Consider role-playing these scenarios at home.</p>
            <h3>Activities to Try</h3>
            <ul>
                <li>Practice "asking to join" phrases during family game time</li>
                <li>Read books about sharing and friendship</li>
                <li>Create opportunities for supervised playdates</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="avatar-message">
            <h3>Strengths Observed</h3>
            <p>Your child demonstrated strong social skills in many scenarios. Continue to reinforce these positive behaviors.</p>
            <h3>Next Steps</h3>
            <ul>
                <li>Encourage your child to help peers who may be struggling in social situations</li>
                <li>Introduce more complex social scenarios through stories and discussions</li>
                <li>Celebrate and acknowledge their thoughtful choices</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)