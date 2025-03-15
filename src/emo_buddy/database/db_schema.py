import sqlite3
import os
import json
import time
from datetime import datetime

# Database configuration - Using an absolute path in the current directory
# This ensures that even if the working directory changes, the database is found
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
DB_PATH = os.path.join(parent_dir, "emobuddy.db")


def get_db_connection():
    """Create a connection to the SQLite database with proper settings"""
    # Ensure database directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

    # Create connection with proper settings
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Returns rows as dictionaries

    # Enable foreign key support
    conn.execute("PRAGMA foreign_keys = ON")

    # Set journal mode to WAL for better concurrency and reliability
    conn.execute("PRAGMA journal_mode = WAL")

    # Set synchronous mode for better reliability
    conn.execute("PRAGMA synchronous = NORMAL")

    return conn


def initialize_database():
    """Create the database schema if it doesn't exist"""
    print(f"Initializing database at: {DB_PATH}")
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Avatar table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS avatars (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        emoji TEXT NOT NULL,
        color TEXT NOT NULL
    )
    ''')

    # Create Scenario table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scenarios (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        image_path TEXT NOT NULL
    )
    ''')

    # Create Phase table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS phases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scenario_id INTEGER NOT NULL,
        phase_id TEXT NOT NULL,
        description TEXT NOT NULL,
        prompt TEXT NOT NULL,
        FOREIGN KEY (scenario_id) REFERENCES scenarios (id),
        UNIQUE (scenario_id, phase_id)
    )
    ''')

    # Create Option table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS options (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phase_id INTEGER NOT NULL,
        option_id TEXT NOT NULL,
        text TEXT NOT NULL,
        icon TEXT,
        emotion TEXT,
        next_phase TEXT,
        FOREIGN KEY (phase_id) REFERENCES phases (id),
        UNIQUE (phase_id, option_id)
    )
    ''')

    # Create Feedback table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phase_id INTEGER NOT NULL,
        option_id TEXT NOT NULL,
        text TEXT NOT NULL,
        positive BOOLEAN NOT NULL,
        guidance BOOLEAN NOT NULL,
        FOREIGN KEY (phase_id) REFERENCES phases (id),
        UNIQUE (phase_id, option_id)
    )
    ''')

    # Create Session table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        avatar_id TEXT,
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_time TIMESTAMP,
        FOREIGN KEY (avatar_id) REFERENCES avatars (id)
    )
    ''')

    # Create Response table to track user responses
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        scenario_id INTEGER NOT NULL,
        phase_id TEXT NOT NULL,
        option_id TEXT NOT NULL,
        emotion TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions (id),
        FOREIGN KEY (scenario_id) REFERENCES scenarios (id)
    )
    ''')

    # Create EmotionDetection table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emotion_detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        emotion TEXT NOT NULL,
        confidence REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions (id)
    )
    ''')

    # Create ParentAlerts table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS parent_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        scenario_id INTEGER NOT NULL,
        phase_id TEXT NOT NULL,
        emotion TEXT NOT NULL,
        resolved BOOLEAN DEFAULT FALSE,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions (id),
        FOREIGN KEY (scenario_id) REFERENCES scenarios (id)
    )
    ''')

    conn.commit()
    conn.close()

    print("Database initialized successfully")


def populate_initial_data():
    """Populate the database with initial data"""
    print("Checking if database needs initial data...")
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if we already have data
    cursor.execute("SELECT COUNT(*) FROM avatars")
    if cursor.fetchone()[0] > 0:
        print("Data already exists, skipping population")
        conn.close()
        return

    print("Populating database with initial data...")
    # Populate avatars
    avatars = [
        {"id": "cat", "name": "Whiskers the Cat", "emoji": "🐱", "color": "#ff9ff3"},
        {"id": "dog", "name": "Buddy the Dog", "emoji": "🐶", "color": "#feca57"},
        {"id": "rabbit", "name": "Hoppy the Rabbit", "emoji": "🐰", "color": "#ff6b6b"},
        {"id": "bear", "name": "Berry the Bear", "emoji": "🐻", "color": "#48dbfb"}
    ]

    for avatar in avatars:
        cursor.execute(
            "INSERT INTO avatars (id, name, emoji, color) VALUES (?, ?, ?, ?)",
            (avatar["id"], avatar["name"], avatar["emoji"], avatar["color"])
        )

    slide_scenario = {
        "id": 1,
        "title": "Taking Turns on the Slide",
        "description": "You see other children taking turns on the slide at the playground. You want to play too.",
        "image_path": "https://placehold.co/600x400/9c88ff/FFF?text=Playground+Slide",
        "phases": [
            # Phase 1: Entering the Playground
            {
                "phase_id": "entering",
                "description": "You and your friend arrive at the playground and see kids taking turns on the slide.",
                "prompt": "Do you want to play on the slide?",
                "options": [
                    {"id": "a", "text": "Yes, I want to play on the slide!", "icon": "🎯", "emotion": "positive",
                     "next_phase": "waiting"},
                    {"id": "b", "text": "No, I want to do something else.", "icon": "🔄", "emotion": "thoughtful",
                     "next_phase": "end_no_slide"}
                ],
                "feedback": {
                    "a": {"text": "Great choice! Let's go to the slide and wait for your turn.", "positive": True,
                          "guidance": False},
                    "b": {"text": "That's okay! There are lots of fun things to do at the playground.",
                          "positive": True, "guidance": False}
                }
            },
            # Phase 2: Waiting in Line
            {
                "phase_id": "waiting",
                "description": "You're standing in line at the slide. There are two children ahead of you.",
                "prompt": "What will you do while you wait?",
                "options": [
                    {"id": "a", "text": "Wait patiently for my turn", "icon": "⏱️", "emotion": "positive",
                     "next_phase": "sliding"},
                    {"id": "b", "text": "Try to cut in line", "icon": "⚡", "emotion": "negative",
                     "next_phase": "waiting_reminder"},
                    {"id": "c", "text": "Get impatient and leave", "icon": "👣", "emotion": "sad",
                     "next_phase": "end_waiting"},
                    {"id": "d", "text": "Count to ten while I wait", "icon": "🔢", "emotion": "thoughtful",
                     "next_phase": "sliding"}
                ],
                "feedback": {
                    "a": {"text": "Excellent job waiting! Your turn is coming up soon.", "positive": True,
                          "guidance": False},
                    "b": {
                        "text": "Cutting in line might make other children upset. Everyone needs to wait for their turn.",
                        "positive": False, "guidance": True},
                    "c": {
                        "text": "It can be hard to wait sometimes. Maybe we could try a breathing exercise next time?",
                        "positive": False, "guidance": True},
                    "d": {"text": "That's a smart way to make waiting easier! Counting helps pass the time.",
                          "positive": True, "guidance": False}
                }
            },
            # Phase 3: Waiting Reminder - special reminder phase
            {
                "phase_id": "waiting_reminder",
                "description": "A child reminds you that everyone needs to wait for their turn.",
                "prompt": "What will you do now?",
                "options": [
                    {"id": "a", "text": "Go back to waiting in line", "icon": "↩️", "emotion": "positive",
                     "next_phase": "sliding"},
                    {"id": "b", "text": "Get upset and leave", "icon": "😠", "emotion": "negative",
                     "next_phase": "end_waiting"}
                ],
                "feedback": {
                    "a": {"text": "That's the right choice! Everyone gets a turn when they wait patiently.",
                          "positive": True, "guidance": False},
                    "b": {
                        "text": "It's important to learn to wait for our turn, even when it's hard. Maybe we can try again later.",
                        "positive": False, "guidance": True}
                }
            },
            # Phase 4: Sliding
            {
                "phase_id": "sliding",
                "description": "It's finally your turn to go down the slide!",
                "prompt": "How do you want to slide down?",
                "options": [
                    {"id": "a", "text": "Slide down happily", "icon": "😄", "emotion": "positive",
                     "next_phase": "exit"},
                    {"id": "b", "text": "Tell the other kids to watch how fast I can go", "icon": "🏎️",
                     "emotion": "thoughtful",
                     "next_phase": "exit"},
                    {"id": "c", "text": "I'm a little scared", "icon": "😨", "emotion": "shy",
                     "next_phase": "sliding_help"}
                ],
                "feedback": {
                    "a": {"text": "Wheee! That was fun! You did a great job taking turns and enjoyed the slide!",
                          "positive": True, "guidance": False},
                    "b": {"text": "It's fun to be excited! Remember that everyone slides at their own speed.",
                          "positive": True, "guidance": True},
                    "c": {
                        "text": "It's okay to feel scared sometimes. Let's think about what might help you feel better.",
                        "positive": True, "guidance": False}
                }
            },
            # Phase 5: Sliding Help
            {
                "phase_id": "sliding_help",
                "description": "You're at the top of the slide feeling a little nervous.",
                "prompt": "What would help you feel better?",
                "options": [
                    {"id": "a", "text": "Ask for help", "icon": "🙋", "emotion": "positive",
                     "next_phase": "exit"},
                    {"id": "b", "text": "Take a deep breath and try", "icon": "😌", "emotion": "thoughtful",
                     "next_phase": "exit"},
                    {"id": "c", "text": "Decide to try something else instead", "icon": "🔄", "emotion": "thoughtful",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {"text": "Great job asking for help! Everyone needs help sometimes.",
                          "positive": True, "guidance": False},
                    "b": {"text": "Deep breaths are a wonderful way to feel braver. You did it!",
                          "positive": True, "guidance": False},
                    "c": {"text": "That's okay! We can try the slide another time when you're feeling ready.",
                          "positive": True, "guidance": False}
                }
            },
            # Exit phases
            {
                "phase_id": "end_waiting",
                "description": "You decided to do something else instead of waiting for the slide.",
                "prompt": "What would you like to do now?",
                "options": [
                    {"id": "a", "text": "Go play on the swings", "icon": "🏃", "emotion": "positive",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {
                        "text": "That's okay! There are lots of fun things to do at the playground. Next time we can practice waiting for our turn.",
                        "positive": True, "guidance": True}
                }
            },
            {
                "phase_id": "end_no_slide",
                "description": "You decided not to play on the slide today.",
                "prompt": "What would you like to do instead?",
                "options": [
                    {"id": "a", "text": "Let's play on something else", "icon": "🎪", "emotion": "positive",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {"text": "That's a fine choice! It's good to know what you want to do.",
                          "positive": True, "guidance": False}
                }
            },
            # Final exit phase - used to mark the scenario as complete
            {
                "phase_id": "exit",
                "description": "You've completed this scenario!",
                "prompt": "Ready to continue?",
                "options": [
                    {"id": "a", "text": "Yes, let's go!", "icon": "👍", "emotion": "positive",
                     "next_phase": "real_exit"}
                ],
                "feedback": {
                    "a": {"text": "Great job with this scenario! You've learned about taking turns.",
                          "positive": True, "guidance": False}
                }
            }
        ]
    }

    sharing_scenario = {
        "id": 2,
        "title": "Sharing Toys at Playtime",
        "description": "You're playing with your favorite toy when another child asks if they can play with it.",
        "image_path": "https://placehold.co/600x400/9c88ff/FFF?text=Sharing+Toys",
        "phases": [
            # Phase 1: Initial Request
            {
                "phase_id": "entering",
                "description": "You're playing with your favorite toy car when another child comes up to you.",
                "prompt": "The child says, 'Can I play with your toy?'",
                "options": [
                    {"id": "a", "text": "Sure, you can have a turn!", "icon": "🤝", "emotion": "positive",
                     "next_phase": "sharing"},
                    {"id": "b", "text": "No! It's mine!", "icon": "😠", "emotion": "negative",
                     "next_phase": "reminder"},
                    {"id": "c", "text": "Maybe in a few minutes when I'm done.", "icon": "⏱️", "emotion": "thoughtful",
                     "next_phase": "waiting"}
                ],
                "feedback": {
                    "a": {"text": "That's very kind of you to share! Sharing helps make new friends.", "positive": True,
                          "guidance": False},
                    "b": {
                        "text": "It can be hard to share sometimes. But sharing helps us make friends and is a kind thing to do.",
                        "positive": False, "guidance": True},
                    "c": {
                        "text": "That's a good compromise! You're setting a boundary while still being willing to share later.",
                        "positive": True, "guidance": False}
                }
            },
            # Phase 2: Sharing
            {
                "phase_id": "sharing",
                "description": "You hand the toy to the other child and they start playing with it.",
                "prompt": "What will you do while they're playing with your toy?",
                "options": [
                    {"id": "a", "text": "Ask to play together with the toy", "icon": "👫", "emotion": "positive",
                     "next_phase": "playing_together"},
                    {"id": "b", "text": "Wait quietly for my turn again", "icon": "🧘", "emotion": "thoughtful",
                     "next_phase": "waiting_turn"},
                    {"id": "c", "text": "Find another toy to play with", "icon": "🧸", "emotion": "positive",
                     "next_phase": "new_toy"}
                ],
                "feedback": {
                    "a": {"text": "Great idea! Playing together is even more fun than playing alone.", "positive": True,
                          "guidance": False},
                    "b": {"text": "That's very patient of you! Waiting for your turn shows good self-control.",
                          "positive": True,
                          "guidance": False},
                    "c": {"text": "That's a good choice! Finding another toy shows flexibility.", "positive": True,
                          "guidance": False}
                }
            },
            # Phase 3: Reminder about sharing
            {
                "phase_id": "reminder",
                "description": "The other child looks sad when you say no.",
                "prompt": "Your teacher reminds you about sharing. What will you do now?",
                "options": [
                    {"id": "a", "text": "Offer to share the toy", "icon": "🤲", "emotion": "positive",
                     "next_phase": "sharing"},
                    {"id": "b", "text": "Suggest they can have a turn later", "icon": "⏱️", "emotion": "thoughtful",
                     "next_phase": "waiting"}
                ],
                "feedback": {
                    "a": {"text": "That's a kind choice! It can be hard to share, but you're being very generous.",
                          "positive": True,
                          "guidance": False},
                    "b": {
                        "text": "That's a good compromise. Setting a time to share later helps everyone know what to expect.",
                        "positive": True,
                        "guidance": True}
                }
            },
            # Phase 4: Waiting
            {
                "phase_id": "waiting",
                "description": "The other child agrees to wait for their turn.",
                "prompt": "How will you let them know when it's their turn?",
                "options": [
                    {"id": "a", "text": "I'll set a timer for 5 minutes", "icon": "⏲️", "emotion": "thoughtful",
                     "next_phase": "timer"},
                    {"id": "b", "text": "I'll give it to them when I'm done with this game", "icon": "🎮",
                     "emotion": "positive",
                     "next_phase": "finish_game"}
                ],
                "feedback": {
                    "a": {
                        "text": "Setting a timer is a great way to take turns fairly! Everyone knows when their turn will come.",
                        "positive": True,
                        "guidance": False},
                    "b": {
                        "text": "That's good planning! Finishing what you're doing and then sharing is a nice balance.",
                        "positive": True,
                        "guidance": False}
                }
            },
            # More phases for other paths
            {
                "phase_id": "playing_together",
                "description": "You and the other child are now playing with the toy together.",
                "prompt": "How do you feel about playing together?",
                "options": [
                    {"id": "a", "text": "This is more fun than playing alone!", "icon": "😄", "emotion": "positive",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {
                        "text": "You're right! Playing together often makes games more fun. You've made a new friend by sharing.",
                        "positive": True,
                        "guidance": False}
                }
            },
            {
                "phase_id": "waiting_turn",
                "description": "You're waiting for your turn with the toy.",
                "prompt": "The other child has been playing for a while. What now?",
                "options": [
                    {"id": "a", "text": "Politely ask if I can have my turn now", "icon": "🙋", "emotion": "positive",
                     "next_phase": "exit"},
                    {"id": "b", "text": "Continue waiting patiently", "icon": "😌", "emotion": "positive",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {"text": "Good job asking politely! It's okay to speak up when you've been waiting a while.",
                          "positive": True,
                          "guidance": False},
                    "b": {"text": "You're being very patient! Sharing sometimes means waiting your turn.",
                          "positive": True,
                          "guidance": False}
                }
            },
            {
                "phase_id": "new_toy",
                "description": "You found another toy to play with while the child plays with your first toy.",
                "prompt": "The child comes to give your toy back. What do you say?",
                "options": [
                    {"id": "a", "text": "Thank you for returning my toy!", "icon": "🙏", "emotion": "positive",
                     "next_phase": "exit"},
                    {"id": "b", "text": "Do you want to play with this toy now?", "icon": "🎁", "emotion": "positive",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {"text": "Saying thank you is a great way to show appreciation when someone returns your toy.",
                          "positive": True,
                          "guidance": False},
                    "b": {"text": "You're being very generous by offering to share your new toy too! That's very kind.",
                          "positive": True,
                          "guidance": False}
                }
            },
            {
                "phase_id": "timer",
                "description": "The timer goes off after 5 minutes.",
                "prompt": "It's time to switch. What do you do?",
                "options": [
                    {"id": "a", "text": "Hand over the toy right away", "icon": "⏰", "emotion": "positive",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {
                        "text": "Excellent! You kept your promise and shared when the timer went off. That's being reliable and fair.",
                        "positive": True,
                        "guidance": False}
                }
            },
            {
                "phase_id": "finish_game",
                "description": "You finish playing your game with the toy.",
                "prompt": "What will you do now?",
                "options": [
                    {"id": "a", "text": "Give the toy to the waiting child", "icon": "🤲", "emotion": "positive",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {
                        "text": "You kept your promise! Sharing after you finished is a great way to be fair and kind.",
                        "positive": True,
                        "guidance": False}
                }
            },
            # Final exit phase
            {
                "phase_id": "exit",
                "description": "You've completed this scenario!",
                "prompt": "Ready to continue?",
                "options": [
                    {"id": "a", "text": "Yes, let's go!", "icon": "👍", "emotion": "positive",
                     "next_phase": "real_exit"}
                ],
                "feedback": {
                    "a": {"text": "Great job with this scenario! You've learned about sharing and taking turns.",
                          "positive": True,
                          "guidance": False}
                }
            }
        ]
    }

    friends_scenario = {
        "id": 3,
        "title": "Making New Friends at School",
        "description": "It's your first day at a new school and you want to make friends during recess.",
        "image_path": "https://placehold.co/600x400/9c88ff/FFF?text=New+School+Friends",
        "phases": [
            # Phase 1: First Recess
            {
                "phase_id": "entering",
                "description": "It's recess time and you see kids playing in different groups.",
                "prompt": "What would you like to do?",
                "options": [
                    {"id": "a", "text": "Go introduce yourself to a group", "icon": "🙋", "emotion": "positive",
                     "next_phase": "introduce"},
                    {"id": "b", "text": "Watch what games they're playing first", "icon": "👀", "emotion": "thoughtful",
                     "next_phase": "observe"},
                    {"id": "c", "text": "Play by yourself for now", "icon": "🧩", "emotion": "shy",
                     "next_phase": "solo_play"}
                ],
                "feedback": {
                    "a": {"text": "That's brave! Introducing yourself is a great way to make new friends.",
                          "positive": True,
                          "guidance": False},
                    "b": {"text": "Good thinking! Watching first can help you understand what games they're playing.",
                          "positive": True,
                          "guidance": False},
                    "c": {
                        "text": "That's okay! Sometimes it's nice to play by yourself while you get comfortable in a new place.",
                        "positive": True,
                        "guidance": False}
                }
            },
            # Phase 2: Introduction
            {
                "phase_id": "introduce",
                "description": "You approach a group of children playing with a ball.",
                "prompt": "What do you say to them?",
                "options": [
                    {"id": "a", "text": "Hi, I'm new here. Can I play with you?", "icon": "🗣️", "emotion": "positive",
                     "next_phase": "joining"},
                    {"id": "b", "text": "Can I have a turn with the ball?", "icon": "🏀", "emotion": "thoughtful",
                     "next_phase": "ball_request"},
                    {"id": "c", "text": "Your game looks fun!", "icon": "🤩", "emotion": "positive",
                     "next_phase": "compliment"}
                ],
                "feedback": {
                    "a": {"text": "Perfect introduction! You told them you're new and asked to join politely.",
                          "positive": True,
                          "guidance": False},
                    "b": {
                        "text": "Asking for a turn is one way to join, but introducing yourself first might be more friendly.",
                        "positive": True,
                        "guidance": True},
                    "c": {"text": "Great start! Complimenting their game is a friendly way to begin a conversation.",
                          "positive": True,
                          "guidance": False}
                }
            },
            # Phase 3: Observation
            {
                "phase_id": "observe",
                "description": "You watch the children playing a game with a ball. They seem to be taking turns throwing it.",
                "prompt": "What will you do now?",
                "options": [
                    {"id": "a", "text": "Ask if you can join their game", "icon": "🙌", "emotion": "positive",
                     "next_phase": "joining"},
                    {"id": "b", "text": "Keep watching a bit longer", "icon": "🧐", "emotion": "thoughtful",
                     "next_phase": "continue_observing"}
                ],
                "feedback": {
                    "a": {
                        "text": "Good choice! Now that you understand their game, asking to join is a great next step.",
                        "positive": True,
                        "guidance": False},
                    "b": {"text": "That's okay too. Taking your time to feel comfortable is perfectly fine.",
                          "positive": True,
                          "guidance": False}
                }
            },
            # More paths and phases
            {
                "phase_id": "solo_play",
                "description": "You find a quiet spot and start playing on your own. After a while, another child notices you.",
                "prompt": "The child asks what you're playing. What do you say?",
                "options": [
                    {"id": "a", "text": "I'm just exploring. Do you want to join me?", "icon": "🔍",
                     "emotion": "positive",
                     "next_phase": "new_friend"},
                    {"id": "b", "text": "I'm playing my own game.", "icon": "🎮", "emotion": "thoughtful",
                     "next_phase": "explain_game"}
                ],
                "feedback": {
                    "a": {
                        "text": "That's a wonderful invitation! You've turned solo play into a chance to make a friend.",
                        "positive": True,
                        "guidance": False},
                    "b": {
                        "text": "Good conversation starter. Telling them about your game might make them interested in playing with you.",
                        "positive": True,
                        "guidance": False}
                }
            },
            {
                "phase_id": "joining",
                "description": "The children welcome you to join their game.",
                "prompt": "How do you feel about joining their game?",
                "options": [
                    {"id": "a", "text": "Excited to play and make new friends", "icon": "😄", "emotion": "positive",
                     "next_phase": "playing_game"},
                    {"id": "b", "text": "A little nervous but happy they said yes", "icon": "😊", "emotion": "shy",
                     "next_phase": "playing_game"}
                ],
                "feedback": {
                    "a": {"text": "Great attitude! Being enthusiastic makes games more fun for everyone.",
                          "positive": True,
                          "guidance": False},
                    "b": {
                        "text": "It's normal to feel nervous in a new situation. Being brave enough to join despite feeling shy is wonderful!",
                        "positive": True,
                        "guidance": False}
                }
            },
            {
                "phase_id": "ball_request",
                "description": "The children look at each other, then one of them asks who you are.",
                "prompt": "How do you respond?",
                "options": [
                    {"id": "a", "text": "I'm [name] and I'm new here. Can I play with you?", "icon": "👋",
                     "emotion": "positive",
                     "next_phase": "joining"},
                    {"id": "b", "text": "I just wanted to play with the ball.", "icon": "🏀", "emotion": "thoughtful",
                     "next_phase": "clarify_request"}
                ],
                "feedback": {
                    "a": {"text": "Perfect! Introducing yourself helps them get to know you better.", "positive": True,
                          "guidance": False},
                    "b": {
                        "text": "It might help to introduce yourself first. People usually want to know who they're playing with.",
                        "positive": False,
                        "guidance": True}
                }
            },
            {
                "phase_id": "compliment",
                "description": "The children smile and thank you. One of them asks if you want to play.",
                "prompt": "What do you say?",
                "options": [
                    {"id": "a", "text": "Yes, I'd love to! I'm [name].", "icon": "🤗", "emotion": "positive",
                     "next_phase": "joining"}
                ],
                "feedback": {
                    "a": {
                        "text": "Excellent! Your friendly compliment led to an invitation, and you responded perfectly.",
                        "positive": True,
                        "guidance": False}
                }
            },
            {
                "phase_id": "continue_observing",
                "description": "You watch a bit longer and learn the rules of their game.",
                "prompt": "One child notices you watching and waves. What do you do?",
                "options": [
                    {"id": "a", "text": "Wave back and approach them", "icon": "👋", "emotion": "positive",
                     "next_phase": "introduce"},
                    {"id": "b", "text": "Smile but stay where you are", "icon": "😊", "emotion": "shy",
                     "next_phase": "they_approach"}
                ],
                "feedback": {
                    "a": {"text": "Good decision! Their wave was an invitation, and you responded in a friendly way.",
                          "positive": True,
                          "guidance": False},
                    "b": {
                        "text": "That's okay too. Smiling shows you're friendly even if you're not ready to approach yet.",
                        "positive": True,
                        "guidance": False}
                }
            },
            {
                "phase_id": "they_approach",
                "description": "The child who waved comes over to you.",
                "prompt": "They ask if you want to play with them. What do you say?",
                "options": [
                    {"id": "a", "text": "Yes, thank you for asking!", "icon": "🙏", "emotion": "positive",
                     "next_phase": "joining"}
                ],
                "feedback": {
                    "a": {
                        "text": "Perfect response! Sometimes others will invite you to play, and you accepted politely.",
                        "positive": True,
                        "guidance": False}
                }
            },
            {
                "phase_id": "explain_game",
                "description": "You tell the child about your game. They seem interested.",
                "prompt": "What will you do next?",
                "options": [
                    {"id": "a", "text": "Ask if they want to play with you", "icon": "🤝", "emotion": "positive",
                     "next_phase": "new_friend"},
                    {"id": "b", "text": "Keep playing by yourself", "icon": "🧍", "emotion": "thoughtful",
                     "next_phase": "stay_solo"}
                ],
                "feedback": {
                    "a": {"text": "Great idea! Inviting them to join is a friendly way to make a new friend.",
                          "positive": True,
                          "guidance": False},
                    "b": {
                        "text": "That's okay if you prefer to play alone right now. You can always make friends later when you feel ready.",
                        "positive": True,
                        "guidance": True}
                }
            },
            {
                "phase_id": "clarify_request",
                "description": "The children seem unsure about letting you play.",
                "prompt": "One child suggests you should introduce yourself first. What do you do?",
                "options": [
                    {"id": "a", "text": "Tell them your name and that you're new", "icon": "👋", "emotion": "positive",
                     "next_phase": "joining"},
                    {"id": "b", "text": "Walk away and find something else to do", "icon": "🚶", "emotion": "sad",
                     "next_phase": "solo_play"}
                ],
                "feedback": {
                    "a": {
                        "text": "Great choice! Introducing yourself helps others feel comfortable including you in their game.",
                        "positive": True,
                        "guidance": False},
                    "b": {
                        "text": "It can be hard when things don't go as planned. Next time, try introducing yourself first - it usually helps!",
                        "positive": False,
                        "guidance": True}
                }
            },
            {
                "phase_id": "new_friend",
                "description": "You and your new friend start playing together.",
                "prompt": "How do you feel about making a new friend?",
                "options": [
                    {"id": "a", "text": "Happy and excited!", "icon": "😄", "emotion": "positive",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {"text": "Making new friends feels great! You did a wonderful job being open and friendly.",
                          "positive": True,
                          "guidance": False}
                }
            },
            {
                "phase_id": "stay_solo",
                "description": "You continue playing by yourself. The other child watches for a moment, then leaves to play elsewhere.",
                "prompt": "How do you feel now?",
                "options": [
                    {"id": "a", "text": "I'm having fun on my own", "icon": "😌", "emotion": "thoughtful",
                     "next_phase": "exit"},
                    {"id": "b", "text": "Maybe I should have invited them to play", "icon": "🤔",
                     "emotion": "thoughtful",
                     "next_phase": "reconsider"}
                ],
                "feedback": {
                    "a": {
                        "text": "It's perfectly okay to enjoy playing by yourself sometimes. You can always make friends when you're ready.",
                        "positive": True,
                        "guidance": False},
                    "b": {
                        "text": "That's a thoughtful reflection. Inviting others to play is usually a good way to make friends, but you can always try next time.",
                        "positive": True,
                        "guidance": True}
                }
            },
            {
                "phase_id": "reconsider",
                "description": "You think about inviting someone to play with you.",
                "prompt": "What will you do at the next recess?",
                "options": [
                    {"id": "a", "text": "Try to make a friend by inviting someone to play", "icon": "🤝",
                     "emotion": "positive",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {
                        "text": "That's a wonderful plan! Learning from our experiences helps us grow. You'll have another chance to make friends tomorrow.",
                        "positive": True,
                        "guidance": False}
                }
            },
            {
                "phase_id": "playing_game",
                "description": "You're playing the ball game with your new friends.",
                "prompt": "One child shows you a special trick with the ball. What do you do?",
                "options": [
                    {"id": "a", "text": "Say 'Wow, that's cool! Can you show me how?'", "icon": "🤩",
                     "emotion": "positive",
                     "next_phase": "learn_trick"},
                    {"id": "b", "text": "Try to do an even better trick", "icon": "🏆", "emotion": "thoughtful",
                     "next_phase": "show_off"}
                ],
                "feedback": {
                    "a": {"text": "Great response! Showing interest and asking to learn is a friendly way to connect.",
                          "positive": True,
                          "guidance": False},
                    "b": {
                        "text": "It's natural to want to impress new friends, but being competitive might not be the best first impression. Showing interest in their skills can help build stronger friendships.",
                        "positive": False,
                        "guidance": True}
                }
            },
            {
                "phase_id": "learn_trick",
                "description": "Your new friend teaches you their special trick with the ball.",
                "prompt": "How do you feel about learning from your new friend?",
                "options": [
                    {"id": "a", "text": "Happy to learn something new together", "icon": "😊", "emotion": "positive",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {
                        "text": "That's a great attitude! Learning from each other is part of what makes friendships special.",
                        "positive": True,
                        "guidance": False}
                }
            },
            {
                "phase_id": "show_off",
                "description": "You try to do an impressive trick, but the ball goes wild and almost hits another child.",
                "prompt": "What do you do next?",
                "options": [
                    {"id": "a", "text": "Apologize to everyone", "icon": "🙏", "emotion": "thoughtful",
                     "next_phase": "apologize"},
                    {"id": "b", "text": "Laugh it off", "icon": "😅", "emotion": "thoughtful",
                     "next_phase": "laugh_reaction"}
                ],
                "feedback": {
                    "a": {"text": "Good choice! Apologizing when we make a mistake shows respect for others.",
                          "positive": True,
                          "guidance": False},
                    "b": {
                        "text": "Sometimes accidents happen, but it's important to make sure everyone is okay and to apologize if someone could have been hurt.",
                        "positive": False,
                        "guidance": True}
                }
            },
            {
                "phase_id": "apologize",
                "description": "You apologize for the wild throw. The other children say it's okay.",
                "prompt": "What will you do now?",
                "options": [
                    {"id": "a", "text": "Ask if they can show you how to do the trick properly", "icon": "🙌",
                     "emotion": "positive",
                     "next_phase": "learn_trick"},
                    {"id": "b", "text": "Take a step back and play more carefully", "icon": "👣",
                     "emotion": "thoughtful",
                     "next_phase": "exit"}
                ],
                "feedback": {
                    "a": {
                        "text": "Excellent choice! Being humble and asking for help turns a mistake into a chance to learn and connect.",
                        "positive": True,
                        "guidance": False},
                    "b": {
                        "text": "Being more careful is a good idea. It shows you care about everyone's safety and enjoyment.",
                        "positive": True,
                        "guidance": False}
                }
            },
            {
                "phase_id": "laugh_reaction",
                "description": "The other children don't seem to find it funny and look concerned.",
                "prompt": "One child asks if you're going to say sorry. What do you do?",
                "options": [
                    {"id": "a", "text": "Apologize sincerely", "icon": "🙏", "emotion": "thoughtful",
                     "next_phase": "apologize"}
                ],
                "feedback": {
                    "a": {
                        "text": "That's the right thing to do. When our actions might have hurt someone, it's important to apologize even if it was an accident.",
                        "positive": True,
                        "guidance": True}
                }
            },
            # Final exit phase
            {
                "phase_id": "exit",
                "description": "You've completed this scenario!",
                "prompt": "Ready to continue?",
                "options": [
                    {"id": "a", "text": "Yes, let's go!", "icon": "👍", "emotion": "positive",
                     "next_phase": "real_exit"}
                ],
                "feedback": {
                    "a": {"text": "Great job with this scenario! You've learned about making friends in new places.",
                          "positive": True,
                          "guidance": False}
                }
            }
        ]
    }

    # Insert scenario
    for scenario in [slide_scenario, sharing_scenario, friends_scenario]:
        # Insert the scenario
        cursor.execute(
            "INSERT INTO scenarios (id, title, description, image_path) VALUES (?, ?, ?, ?)",
            (scenario["id"], scenario["title"], scenario["description"], scenario["image_path"])
        )

        # Insert phases, options, and feedback
        for phase in scenario["phases"]:
            cursor.execute(
                "INSERT INTO phases (scenario_id, phase_id, description, prompt) VALUES (?, ?, ?, ?)",
                (scenario["id"], phase["phase_id"], phase["description"], phase["prompt"])
            )

            # Get the phase primary key
            cursor.execute("SELECT last_insert_rowid()")
            phase_pk = cursor.fetchone()[0]

            # Insert options
            for option in phase["options"]:
                cursor.execute(
                    "INSERT INTO options (phase_id, option_id, text, icon, emotion, next_phase) VALUES (?, ?, ?, ?, ?, ?)",
                    (phase_pk, option["id"], option["text"], option.get("icon"), option.get("emotion"),
                     option.get("next_phase"))
                )

            # Insert feedback
            for option_id, feedback in phase["feedback"].items():
                cursor.execute(
                    "INSERT INTO feedback (phase_id, option_id, text, positive, guidance) VALUES (?, ?, ?, ?, ?)",
                    (phase_pk, option_id, feedback["text"], feedback["positive"], feedback["guidance"])
                )


    conn.commit()
    conn.close()

    print("Initial data populated successfully")


if __name__ == "__main__":
    initialize_database()
    populate_initial_data()