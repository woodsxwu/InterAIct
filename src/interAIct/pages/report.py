import streamlit as st
import pandas as pd
from database import db_service as db
from utils.session_manager import get_session_report, reset_session
from database.scenario_dao import ScenarioDAO


def calculate_attention_score(attention_df):
    """Calculate an attention score from 0-10 based on attention metrics"""
    if len(attention_df) == 0:
        return 0
    
    # Weight different attention states
    weights = {
        "Attentive": 10,
        "Partially Attentive": 6,
        "Not Attentive": 2,
        "Unknown": 5
    }
    
    # Calculate weighted average
    total_weight = 0
    total_score = 0
    
    for state, count in attention_df['attention_state'].value_counts().items():
        score = weights.get(state, 5)
        total_score += score * count
        total_weight += count
    
    if total_weight == 0:
        return 0
        
    return total_score / total_weight


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


def generate_emotion_timeline(emotion_detections):
    """Generate a timeline of emotions from emotion detection data"""
    if not emotion_detections:
        return pd.DataFrame()
    
    # Create DataFrame
    emotion_df = pd.DataFrame(emotion_detections)
    
    # Add sequential index to represent time progression
    emotion_df['sequence'] = range(len(emotion_df))
    
    # Convert to proper types
    if 'confidence' in emotion_df.columns:
        emotion_df['confidence'] = emotion_df['confidence'].astype(float)
    
    # Add a numeric value for each emotion for charting
    # This maps the original emotion labels to numeric values for visualization
    emotion_mapping = {
        'neutral': 0,
        'natural': 0,
        'happy': 1,
        'joy': 1,
        'surprise': 0.5,
        'sad': -1,
        'sadness': -1,
        'angry': -1,
        'anger': -1,
        'fear': -1
    }
    
    if 'emotion' in emotion_df.columns:
        # Add numeric values for charting
        emotion_df['emotion_value'] = emotion_df['emotion'].map(
            lambda e: emotion_mapping.get(e.lower() if isinstance(e, str) else 'neutral', 0)
        )
    
    return emotion_df


def generate_attention_analysis(attention_metrics):
    """Generate analysis from attention metrics data"""
    if not attention_metrics:
        return pd.DataFrame(), 0
    
    # Create DataFrame
    attn_df = pd.DataFrame(attention_metrics)
    
    # Add sequential index to represent time progression
    attn_df['sequence'] = range(len(attn_df))
    
    # Calculate overall attention score
    attention_score = calculate_attention_score(attn_df)
    
    return attn_df, attention_score


def generate_detailed_report():
    """Generate a session walkthrough including mood shifts and decision events."""

    if "responses" not in st.session_state or "emotion_timeline" not in st.session_state:
        st.warning("No session data found.")
        return pd.DataFrame()

    report_data = []
    emotion_events = {entry["timestamp"]: entry for entry in st.session_state.emotion_timeline}

    for resp in st.session_state.responses:
        timestamp = resp.get("timestamp", "Unknown")
        mood_event = emotion_events.get(timestamp, None)

        report_data.append({
            "Timestamp": timestamp,
            "Scenario": resp.get("scenario_id", "Unknown"),
            "Phase": resp.get("phase_id", "Unknown"),
            "Child's Response": resp.get("response", "Unknown"),
            "Detected Emotion": mood_event["emotion"].capitalize() if mood_event else "No Change",
            "Confidence": mood_event["confidence"] if mood_event else "N/A"
        })

    return pd.DataFrame(report_data)


def show_report():
    st.markdown("<h1>Social Skills Learning Report</h1>", unsafe_allow_html=True)
    st.markdown("<p>This report provides insights into the child's responses to social scenarios.</p>",
                unsafe_allow_html=True)

    # Try to get the session report from database
    try:
        report_data = get_session_report()
    except Exception as e:
        st.error(f"Error retrieving report data: {e}")
        report_data = None

    # If database report is available, use it
    if report_data and report_data.get('responses'):
        # Create DataFrame from the report data
        responses = report_data['responses']
        emotion_detections = report_data.get('emotion_detections', [])
        attention_metrics = report_data.get('attention_metrics', [])

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
                    # Just capitalize emotions without remapping
                    display_df['Detected Emotion'] = display_df['Detected Emotion'].apply(
                        lambda x: x.capitalize() if x else "Unknown")

                # Display responses table
                st.subheader("Response Summary")
                st.dataframe(display_df, use_container_width=True)

                # Summary statistics
                positive_choices = (display_df.get("Positive Choice", pd.Series(["Yes"])) == "Yes").sum()
                needed_guidance = (display_df.get("Needed Guidance", pd.Series(["No"])) == "Yes").sum()
                total_responses = len(display_df)

                # Display metrics
                st.subheader("Key Metrics")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(label="Total Responses", value=total_responses)
                with col2:
                    st.metric(label="Positive Choices", value=f"{positive_choices}/{total_responses}")
                with col3:
                    st.metric(label="Needed Guidance", value=f"{needed_guidance}/{total_responses}")

                # Display emotion distribution if available
                if emotion_detections:
                    st.subheader("Emotion Analysis")
                    
                    # Process emotion data but keep original labels
                    emotion_df = generate_emotion_timeline(emotion_detections)
                    
                    # Show emotion distribution with capitalized but unmapped emotions
                    emotion_counts = pd.Series([e['emotion'].capitalize() for e in emotion_detections]).value_counts().reset_index()
                    emotion_counts.columns = ['Emotion', 'Count']
                    
                    # Display emotion distribution chart
                    st.bar_chart(emotion_counts.set_index('Emotion'))
                    
                    # Show most common emotions
                    st.markdown(f"**Most frequent emotions:** {', '.join(emotion_counts['Emotion'].head(3).tolist())}")
                    
                    # Add explanation of emotion categories
                    st.markdown("""
                    **Understanding the Emotion Categories:**
                    - **Natural/Neutral**: Calm, balanced emotional state
                    - **Joy/Happy**: Expressing happiness or excitement
                    - **Sadness**: Expressing sadness or disappointment
                    - **Anger**: Expressing frustration or anger
                    - **Fear**: Expressing worry or fear
                    - **Surprise**: Expressing astonishment or surprise
                    """)
                    
                    # Show emotion timeline if there are enough data points
                    if len(emotion_df) > 1 and 'emotion_value' in emotion_df.columns:
                        st.subheader("Emotion Timeline")
                        st.line_chart(emotion_df.set_index('sequence')['emotion_value'])
                        
                        # Add a legend
                        st.markdown("""
                        **Emotion Value Legend:**
                        - 1: Joy/Happy
                        - 0.5: Surprise
                        - 0: Neutral/Natural
                        - -1: Sadness/Anger/Fear
                        """)
                
                # Display attention metrics if available
                if attention_metrics:
                    st.subheader("Attention Analysis")
                    
                    # Process attention data
                    attn_df, attention_score = generate_attention_analysis(attention_metrics)
                    
                    # Display attention score
                    st.metric("Overall Attention Score", f"{attention_score:.1f}/10")
                    
                    # Show attention state distribution
                    attn_counts = pd.Series([a['attention_state'] for a in attention_metrics]).value_counts().reset_index()
                    attn_counts.columns = ['Attention State', 'Count']
                    
                    # Display attention distribution chart
                    st.bar_chart(attn_counts.set_index('Attention State'))
                    
                    # Display attention state descriptions
                    st.markdown("""
                    **Attention States:**
                    - **Attentive**: Child is fully engaged with the content
                    - **Partially Attentive**: Child is somewhat distracted but still participating
                    - **Not Attentive**: Child appears distracted or disengaged
                    """)
                    
                    # Display attention over time if enough data points
                    if len(attn_df) > 5:
                        st.subheader("Attention Over Time")
                        
                        # Create numeric mapping for attention states
                        attention_values = {
                            "Attentive": 10,
                            "Partially Attentive": 5,
                            "Not Attentive": 1,
                            "Unknown": 3
                        }
                        
                        # Convert attention states to numeric values
                        if 'attention_state' in attn_df.columns:
                            attn_df['attention_value'] = attn_df['attention_state'].map(
                                lambda x: attention_values.get(x, 3)
                            )
                            
                            # Display line chart
                            st.line_chart(attn_df.set_index('sequence')['attention_value'])
                    
                    # Interpret attention score
                    if attention_score >= 8:
                        st.success("The child maintained excellent attention throughout the session!")
                    elif attention_score >= 6:
                        st.info("The child showed good attention with some fluctuations.")
                    elif attention_score >= 4:
                        st.warning("The child showed moderate attention that could be improved.")
                    else:
                        st.error("The child had difficulty maintaining attention during the session.")

                # Show recommendations based on performance
                show_recommendations(positive_choices, needed_guidance, total_responses, attention_score if attention_metrics else None)
            else:
                st.warning("Response data is missing expected columns. Using simplified report format.")
                alt_df = generate_report(unique_responses)
                st.dataframe(alt_df, use_column_width=True)
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

            # Just capitalize emotions without remapping
            emotion = resp.get('emotion', 'Unknown')
            if isinstance(emotion, str):
                emotion = emotion.capitalize()

            report_data.append({
                "Scenario": scenario_title,
                "Phase": resp.get('phase_id', 'Unknown'),
                "Child's Response": f"Option {resp.get('response', 'Unknown')}",
                "Detected Emotion": emotion,
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

        # Display emotion distribution if available
        if 'Detected Emotion' in report_df.columns:
            emotion_counts = report_df['Detected Emotion'].value_counts().reset_index()
            emotion_counts.columns = ['Emotion', 'Count']

            st.subheader("Emotion Distribution")
            st.bar_chart(emotion_counts.set_index('Emotion'))
            
            # Show most common emotions
            st.markdown(f"**Most frequent emotions:** {', '.join(emotion_counts['Emotion'].head(3).tolist())}")
            
            # Add explanation of emotion categories
            st.markdown("""
            **Understanding the Emotion Categories:**
            - **Natural/Neutral**: Calm, balanced emotional state
            - **Joy/Happy**: Expressing happiness or excitement
            - **Sadness**: Expressing sadness or disappointment
            - **Anger**: Expressing frustration or anger
            - **Fear**: Expressing worry or fear
            - **Surprise**: Expressing astonishment or surprise
            """)

        # Use fallback for attention if available in session state
        if hasattr(st.session_state, 'detected_attention') and st.session_state.detected_attention:
            st.subheader("Attention Analysis")
            attn_df = pd.DataFrame(st.session_state.detected_attention)
            
            if 'attention_state' in attn_df.columns:
                attn_counts = attn_df['attention_state'].value_counts().reset_index()
                attn_counts.columns = ['Attention State', 'Count']
                
                st.bar_chart(attn_counts.set_index('Attention State'))
                
                # Calculate attention score
                attention_score = calculate_attention_score(attn_df)
                st.metric("Attention Score", f"{attention_score:.1f}/10")
                
                # Display attention state descriptions
                st.markdown("""
                **Attention States:**
                - **Attentive**: Child is fully engaged with the content
                - **Partially Attentive**: Child is somewhat distracted but still participating
                - **Not Attentive**: Child appears distracted or disengaged
                """)
            else:
                st.info("Attention data is incomplete.")
        
        # Show generic recommendations
        show_recommendations(total_responses, 0, total_responses)
    else:
        st.info("No scenarios have been completed yet. Complete some scenarios to see your report.")


def show_recommendations(positive_choices, needed_guidance, total_responses, attention_score=None):
    """Display personalized recommendations based on the child's performance"""
    st.markdown("<h2>Recommendations for Parents/Teachers</h2>", unsafe_allow_html=True)

    # Generate recommendations based on both responses and attention
    recommendations = []
    strengths = []
    
    # Response-based recommendations
    if needed_guidance > total_responses / 2:
        recommendations.append("Consider role-playing social scenarios at home to reinforce positive interactions.")
        recommendations.append("Practice 'asking to join' and sharing phrases during family time.")
        recommendations.append("Read books about sharing and friendship together.")
    else:
        strengths.append("Your child demonstrates strong social decision-making skills.")
        strengths.append("They show good understanding of appropriate social behaviors in various situations.")
    
    # Attention-based recommendations
    if attention_score is not None:
        if attention_score < 5:
            recommendations.append("Try short learning sessions with frequent breaks to help maintain attention.")
            recommendations.append("Use more visual and interactive learning activities that require active participation.")
            recommendations.append("Consider activities to improve focus and attention like simple mindfulness exercises.")
        elif attention_score >= 8:
            strengths.append("Your child shows excellent ability to maintain attention during learning activities.")
            strengths.append("They engage well with the presented content and stay focused throughout.")
    
    # Display strengths section
    if strengths:
        st.markdown("""
        <div class="avatar-message">
            <h3>Strengths Observed</h3>
            <ul>
        """ + "".join([f"<li>{strength}</li>" for strength in strengths]) + """
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Display recommendations section
    if recommendations:
        st.markdown("""
        <div class="avatar-message">
            <h3>Suggested Activities</h3>
            <ul>
        """ + "".join([f"<li>{rec}</li>" for rec in recommendations]) + """
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Always include next steps
    st.markdown("""
    <div class="avatar-message">
        <h3>Next Steps</h3>
        <ul>
            <li>Continue using InterAIct regularly to practice different social scenarios</li>
            <li>Discuss the scenarios with your child and ask how they might apply what they've learned</li>
            <li>Look for opportunities to praise your child when they demonstrate good social skills in real life</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)


def plot_emotion_timeline():
    """Plot the child's emotional progression over time using Streamlit's built-in charts."""
    if "emotion_timeline" not in st.session_state or not st.session_state.emotion_timeline:
        st.warning("No emotion tracking data available.")
        return

    # Create DataFrame from emotion timeline
    emotion_data = []
    
    for entry in st.session_state.emotion_timeline:
        # Just capitalize the emotion without remapping
        emotion = entry["emotion"]
        if isinstance(emotion, str):
            emotion = emotion.capitalize()
        else:
            emotion = "Unknown"
        
        emotion_data.append({
            "Timestamp": entry["timestamp"],
            "Emotion": emotion,
            "Confidence": entry["confidence"]
        })

    df = pd.DataFrame(emotion_data)

    # Display emotion timeline
    st.subheader("Emotional Changes Over Time")

    # Display as a line chart using Streamlit
    if len(df) > 0:
        # Create a numeric mapping for emotions for the chart
        emotion_mapping = {emotion: i for i, emotion in enumerate(df['Emotion'].unique())}
        df['Emotion_Value'] = df['Emotion'].map(emotion_mapping)

        # Display the line chart
        st.line_chart(df.set_index('Timestamp')['Emotion_Value'])

        # Add a legend explaining the numeric mapping
        st.write("Emotion Legend:")
        for emotion, value in emotion_mapping.items():
            st.write(f"{value}: {emotion}")
    else:
        st.info("Not enough emotion data to display a timeline.")


def generate_downloadable_report():
    """Generate a downloadable report in CSV format instead of PDF."""
    if "responses" not in st.session_state:
        st.warning("No data available to generate a report.")
        return

    # Create a DataFrame from session responses
    report_data = []
    
    for resp in st.session_state.responses:
        # Just capitalize the emotion without remapping
        emotion = resp.get('emotion', 'Unknown')
        if isinstance(emotion, str):
            emotion = emotion.capitalize()
        else:
            emotion = "Unknown"
        
        report_data.append({
            "Scenario": resp.get('scenario_id', 'Unknown'),
            "Phase": resp.get('phase_id', 'Unknown'),
            "Response": resp.get('response', 'Unknown'),
            "Emotion": emotion,
            "Timestamp": resp.get('timestamp', 'Unknown')
        })

    if not report_data:
        st.warning("No response data available to generate a report.")
        return

    # Create DataFrame and convert to CSV
    df = pd.DataFrame(report_data)
    csv = df.to_csv(index=False)

    # Add download button
    st.download_button(
        label="Download Report as CSV",
        data=csv,
        file_name="social_skills_report.csv",
        mime="text/csv"
    )