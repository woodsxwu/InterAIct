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
    
    # Create AttentionMetrics table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attention_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        attention_state TEXT NOT NULL,
        confidence REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions (id)
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

    # [Rest of the existing populate_initial_data function remains unchanged]
    # Add the Taking Turns scenario
    cursor.execute(
        "INSERT INTO scenarios (id, title, description, image_path) VALUES (?, ?, ?, ?)",
        (
            1, 
            "Taking Turns",
            "Learn how to take turns and share toys with friends",
            "images/scenario_taking_turns.jpg"  # You'll need to provide this image
        )
    )

    # Add phases for Taking Turns scenario
    phases = [
        # Stage 1: Taking Turns with Toys
        {
            "scenario_id": 3,
            "phase_id": "toys",
            "description": "Taking Turns with Toys",
            "prompt": "Hi there! Do you like playing with toys? I love playing with toys too! If we both want to play with the same toy, what should we do?"
        },
        # Stage 2: Trading Toys
        {
            "scenario_id": 3,
            "phase_id": "trading",
            "description": "Trading Toys",
            "prompt": "If my friend is playing with a toy I like, what can I do? I can try trading a toy! That way, we both get to play with something fun!"
        },
        # Stage 3: Using a Timer for Turns
        {
            "scenario_id": 3,
            "phase_id": "timer",
            "description": "Using a Timer for Turns",
            "prompt": "Sometimes, when we want to play with a toy, someone else is already using it. What can we do? We can use a timer so everyone gets a turn! Do you think that's fair?"
        },
        # Stage 4: Waiting for My Turn
        {
            "scenario_id": 3,
            "phase_id": "waiting",
            "description": "Waiting for My Turn",
            "prompt": "Sometimes, our friend isn't ready to share yet, and that's okay! What should we do while we wait?"
        },
        # Stage 5: Asking an Adult for Help
        {
            "scenario_id": 3,
            "phase_id": "adult_help",
            "description": "Asking an Adult for Help",
            "prompt": "If we don't know what to do, we can always ask an adult for help! That way, everything feels fair for everyone."
        },
        # Stage 6: Celebrating Good Choices
        {
            "scenario_id": 3,
            "phase_id": "celebrating",
            "description": "Celebrating Good Choices!",
            "prompt": "Wow! You've learned so much about taking turns! Now, you can practice these skills when playing with friends. Are you ready to have fun?"
        }
    ]

    for phase in phases:
        cursor.execute(
            "INSERT INTO phases (scenario_id, phase_id, description, prompt) VALUES (?, ?, ?, ?)",
            (phase["scenario_id"], phase["phase_id"], phase["description"], phase["prompt"])
        )
        
        # Get the phase ID
        cursor.execute("SELECT id FROM phases WHERE scenario_id = ? AND phase_id = ?", 
                    (phase["scenario_id"], phase["phase_id"]))
        phase_db_id = cursor.fetchone()[0]
        
        # Add options for each phase
        if phase["phase_id"] == "toys":
            options = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "Take the toy from a friend.",
                    "icon": "😬",
                    "emotion": "negative",
                    "next_phase": "trading"  # Move to next phase even if wrong
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "b",
                    "text": "Politely ask, 'Can I have a turn, please?'",
                    "icon": "😊",
                    "emotion": "positive",
                    "next_phase": "trading"  # Move to next phase
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "c",
                    "text": "Walk away without saying anything.",
                    "icon": "😕",
                    "emotion": "neutral",
                    "next_phase": "trading"  # Move to next phase even if wrong
                }
            ]
            
            # Add feedback for each option
            feedback = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "Oh no! If we take the toy without asking, our friend might feel sad. Let's try asking first, okay?",
                    "positive": False,
                    "guidance": True
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "b",
                    "text": "Wow! Great job! Asking nicely makes our friends happy and more willing to share. But sometimes, they might say 'no,' and that's okay! We can wait for our turn.",
                    "positive": True,
                    "guidance": False
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "c",
                    "text": "Hmm, walking away is okay, but if you really want to play, you can try asking first! Maybe your friend will share.",
                    "positive": False,
                    "guidance": True
                }
            ]
        
        elif phase["phase_id"] == "trading":
            options = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "Take the toy from a friend.",
                    "icon": "😬",
                    "emotion": "negative",
                    "next_phase": "timer"
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "b",
                    "text": "Offer to trade with a different toy.",
                    "icon": "😊",
                    "emotion": "positive",
                    "next_phase": "timer"
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "c",
                    "text": "Get upset and walk away.",
                    "icon": "😢",
                    "emotion": "negative",
                    "next_phase": "timer"
                }
            ]
            
            feedback = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "Oh no! If we take something without asking, our friend might feel upset. Let's try offering a trade instead!",
                    "positive": False,
                    "guidance": True
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "b",
                    "text": "Wow! You're so kind! Trading toys is a great way to share and make everyone happy!",
                    "positive": True,
                    "guidance": False
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "c",
                    "text": "I understand, you really want that toy. But how about we ask if they want to trade? That way, both of you can be happy!",
                    "positive": False,
                    "guidance": True
                }
            ]
        
        elif phase["phase_id"] == "timer":
            options = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "Use a timer and wait for a turn.",
                    "icon": "⏱️",
                    "emotion": "positive",
                    "next_phase": "waiting"
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "b",
                    "text": "Keep asking the friend to let me play.",
                    "icon": "🗣️",
                    "emotion": "negative",
                    "next_phase": "waiting"
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "c",
                    "text": "Get upset and leave.",
                    "icon": "😢",
                    "emotion": "negative",
                    "next_phase": "waiting"
                }
            ]
            
            feedback = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "Wow, great job! A timer helps make turn-taking fair. When it beeps, it's your turn to play!",
                    "positive": True,
                    "guidance": False
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "b",
                    "text": "Hmm, asking too much might make our friend feel stressed. Let's try using a timer so we all know when it's our turn!",
                    "positive": False,
                    "guidance": True
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "c",
                    "text": "I know waiting is hard, but using a timer makes turn-taking fair. Let's give it a try!",
                    "positive": False,
                    "guidance": True
                }
            ]
        
        elif phase["phase_id"] == "waiting":
            options = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "Ask my friend to tell me when they're done.",
                    "icon": "🙋",
                    "emotion": "positive",
                    "next_phase": "adult_help"
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "b",
                    "text": "Take the toy anyway.",
                    "icon": "😬",
                    "emotion": "negative",
                    "next_phase": "adult_help"
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "c",
                    "text": "Stand still and get upset.",
                    "icon": "😢",
                    "emotion": "negative",
                    "next_phase": "adult_help"
                }
            ]
            
            feedback = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "That's a smart choice! Now you can play with something else while you wait!",
                    "positive": True,
                    "guidance": False
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "b",
                    "text": "Oh no! Taking the toy might make our friend sad. Let's try asking them first!",
                    "positive": False,
                    "guidance": True
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "c",
                    "text": "Waiting can be tough, but there are so many fun things to do! Let's ask our friend when they'll be done instead!",
                    "positive": False,
                    "guidance": True
                }
            ]
        
        elif phase["phase_id"] == "adult_help":
            options = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "Ask a teacher or parent for help.",
                    "icon": "🧑‍🏫",
                    "emotion": "positive",
                    "next_phase": "celebrating"
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "b",
                    "text": "Yell at my friend.",
                    "icon": "😠",
                    "emotion": "negative",
                    "next_phase": "celebrating"
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "c",
                    "text": "Give up and walk away.",
                    "icon": "😔",
                    "emotion": "negative",
                    "next_phase": "celebrating"
                }
            ]
            
            feedback = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "Great choice! Adults can help make sure everyone gets a turn.",
                    "positive": True,
                    "guidance": False
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "b",
                    "text": "Uh-oh! Yelling might make things worse. Let's try asking an adult instead.",
                    "positive": False,
                    "guidance": True
                },
                {
                    "phase_id": phase_db_id,
                    "option_id": "c",
                    "text": "It's okay to ask for help when we need it! Let's try talking to an adult.",
                    "positive": False,
                    "guidance": True
                }
            ]
        
        elif phase["phase_id"] == "celebrating":
            # For the final celebration phase, we'll create a special option that marks completion
            options = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "I'm ready to play with friends!",
                    "icon": "🎉",
                    "emotion": "positive",
                    "next_phase": "real_exit"  # Special marker for scenario completion
                }
            ]
            
            feedback = [
                {
                    "phase_id": phase_db_id,
                    "option_id": "a",
                    "text": "Fantastic! You've learned all about taking turns. Now you can use these skills when playing with your friends!",
                    "positive": True,
                    "guidance": False
                }
            ]
        
        # Insert options for this phase
        for option in options:
            cursor.execute(
                "INSERT INTO options (phase_id, option_id, text, icon, emotion, next_phase) VALUES (?, ?, ?, ?, ?, ?)",
                (option["phase_id"], option["option_id"], option["text"], option["icon"], option["emotion"], option["next_phase"])
            )
        
        # Insert feedback for this phase
        for fb in feedback:
            cursor.execute(
                "INSERT INTO feedback (phase_id, option_id, text, positive, guidance) VALUES (?, ?, ?, ?, ?)",
                (fb["phase_id"], fb["option_id"], fb["text"], fb["positive"], fb["guidance"])
            )
    
    conn.commit()
    conn.close()

    print("Initial data populated successfully")


if __name__ == "__main__":
    initialize_database()
    populate_initial_data()