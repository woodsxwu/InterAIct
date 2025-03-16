import streamlit as st
import pandas as pd
from database import db_service as db
from database.scenario_dao import ScenarioDAO
from pages.report import generate_report, calculate_attention_score


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
                
                # Display emotion data if available
                if 'emotion_detections' in report_data and report_data['emotion_detections']:
                    st.subheader("Emotion Analysis")
                    
                    # Create DataFrame
                    emotion_df = pd.DataFrame(report_data['emotion_detections'])
                    
                    # Only capitalize the emotion, don't remap it
                    if 'emotion' in emotion_df.columns:
                        emotion_df['emotion'] = emotion_df['emotion'].apply(
                            lambda x: x.capitalize() if isinstance(x, str) else "Unknown"
                        )
                    
                    # Show emotion distribution
                    emotion_counts = emotion_df['emotion'].value_counts().reset_index()
                    emotion_counts.columns = ['Emotion', 'Count']
                    
                    # Display chart
                    st.bar_chart(emotion_counts.set_index('Emotion'))
                    
                    # Show most common emotions
                    st.markdown(f"**Most frequent emotions:** {', '.join(emotion_counts['Emotion'].head(3).tolist())}")
                    
                    # Add detailed description of what the emotions mean
                    st.markdown("""
                    **Understanding the Emotion Categories:**
                    - **Natural/Neutral**: Calm, balanced emotional state
                    - **Joy/Happy**: Expressing happiness or excitement
                    - **Sadness**: Expressing sadness or disappointment
                    - **Anger**: Expressing frustration or anger
                    - **Fear**: Expressing worry or fear
                    - **Surprise**: Expressing astonishment or surprise
                    """)
                
                # Display attention metrics if available
                if 'attention_metrics' in report_data and report_data['attention_metrics']:
                    st.subheader("Attention Analysis")
                    
                    # Create DataFrame
                    attention_df = pd.DataFrame(report_data['attention_metrics'])
                    
                    # Calculate attention score
                    attention_score = calculate_attention_score(attention_df)
                    
                    # Display score
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(label="Overall Attention Score", value=f"{attention_score:.1f}/10")
                    
                    with col2:
                        # Interpret score
                        if attention_score >= 8:
                            attention_quality = "Excellent"
                        elif attention_score >= 6:
                            attention_quality = "Good"
                        elif attention_score >= 4:
                            attention_quality = "Fair"
                        else:
                            attention_quality = "Needs Improvement"
                        
                        st.metric(label="Attention Quality", value=attention_quality)
                    
                    # Show attention distribution
                    attention_counts = attention_df['attention_state'].value_counts().reset_index()
                    attention_counts.columns = ['Attention State', 'Count']
                    
                    # Display chart
                    st.bar_chart(attention_counts.set_index('Attention State'))
                    
                    # Display attention state descriptions
                    st.markdown("""
                    **Attention States:**
                    - **Attentive**: Child is fully engaged with the content
                    - **Partially Attentive**: Child is somewhat distracted but still participating
                    - **Not Attentive**: Child appears distracted or disengaged
                    """)
                    
                    # Display attention over time if enough data points
                    if len(attention_df) > 5:
                        st.subheader("Attention Over Time")
                        
                        # Create numeric mapping for attention states
                        attention_values = {
                            "Attentive": 10,
                            "Partially Attentive": 5,
                            "Not Attentive": 1,
                            "Unknown": 3
                        }
                        
                        # Convert attention states to numeric values
                        if 'attention_state' in attention_df.columns:
                            attention_df['attention_value'] = attention_df['attention_state'].map(
                                lambda x: attention_values.get(x, 3)
                            )
                            
                            # Add sequence number if timestamp isn't usable
                            attention_df['sequence'] = range(len(attention_df))
                            
                            # Display line chart
                            st.line_chart(attention_df.set_index('sequence')['attention_value'])
                    
                    # Recommendations based on attention
                    st.markdown("### Attention Recommendations")
                    
                    if attention_score < 5:
                        st.markdown("""
                        - Consider shorter learning sessions with more frequent breaks
                        - Use more engaging, interactive learning materials
                        - Try activities that specifically target focus and attention
                        - Consider consulting with a specialist if attention difficulties persist
                        """)
                    elif attention_score < 7:
                        st.markdown("""
                        - Mix high-interest activities with more challenging ones
                        - Use visual timers to help maintain focus for set periods
                        - Incorporate movement breaks between learning activities
                        """)
                    else:
                        st.markdown("""
                        - Continue using engaging learning materials
                        - Gradually increase the duration of focused activities
                        - Encourage self-monitoring of attention
                        """)
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
        
        # Attention alerts
        st.markdown("<h3>Attention Monitoring</h3>", unsafe_allow_html=True)
        st.checkbox("Alert when attention drops below threshold", value=True)
        st.slider("Attention alert threshold", min_value=1, max_value=10, value=5, 
                 help="Send alert when attention score drops below this value")

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

            # For emotion, just capitalize it without remapping
            emotion = resp.get('emotion', 'Unknown')
            if isinstance(emotion, str):
                emotion = emotion.capitalize()

            data.append({
                'Scenario': scenario_title,
                'Response': f"Option {resp.get('response', 'Unknown')}",
                'Emotion': emotion,
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
                
            # Check for attention data in session state
            if hasattr(st.session_state, 'detected_attention') and st.session_state.detected_attention:
                st.subheader("Attention Data (Session State)")
                attention_df = pd.DataFrame(st.session_state.detected_attention)
                
                # Calculate simple attention score if possible
                if 'attention_state' in attention_df.columns:
                    attention_score = calculate_attention_score(attention_df)
                    st.metric("Attention Score", f"{attention_score:.1f}/10")
                    
                    # Show distribution
                    attention_counts = attention_df['attention_state'].value_counts().reset_index()
                    attention_counts.columns = ['Attention State', 'Count']
                    st.bar_chart(attention_counts.set_index('Attention State'))
        else:
            st.info("No activity data available yet. Have your child complete some scenarios to see progress.")
    else:
        st.info("No activity data available yet. Have your child complete some scenarios to see progress.")