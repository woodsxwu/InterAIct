import os
import sqlite3
import shutil
import sys
import time
from pathlib import Path


# Define DB_PATH directly in this script to avoid circular imports
current_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(current_dir, "emobuddy.db")


def reset_database(force=False):
    """
    Reset the database to initial state
    
    Args:
        force (bool): If True, skip confirmation prompt
    """
    print("\n========== EmoBuddy Database Reset ==========")
    print(f"Target database: {os.path.abspath(DB_PATH)}")
    
    # Confirmation prompt for safety
    if not force:
        confirm = input("\n⚠️  WARNING: This will delete all data! Continue? (y/n): ")
        if confirm.lower() not in ['y', 'yes']:
            print("Database reset cancelled.")
            return False
    
    print("\n🔄 Starting database reset process...")
    
    # Check if database exists
    if os.path.exists(DB_PATH):
        print(f"📤 Removing existing database: {DB_PATH}")
        
        # Close any open connections
        try:
            conn = sqlite3.connect(DB_PATH)
            # Disable WAL mode to ensure clean shutdown
            conn.execute("PRAGMA journal_mode = DELETE")
            conn.commit()
            conn.close()
            print("✅ Successfully closed open database connections")
        except Exception as e:
            print(f"⚠️  Warning when closing connections: {e}")
        
        # Wait a moment for any background processes
        time.sleep(0.5)
        
        # Remove the database and related files
        try:
            # Remove the main database file
            os.remove(DB_PATH)
            
            # Also remove WAL and SHM files if they exist
            wal_file = f"{DB_PATH}-wal"
            shm_file = f"{DB_PATH}-shm"
            
            for file_path in [wal_file, shm_file]:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"✅ Removed: {file_path}")
                    
            print("✅ All database files removed successfully")
        except Exception as e:
            print(f"❌ Error removing database files: {e}")
            print("Attempting to continue...")

    # Remove session data directory
    session_dir = os.path.join(current_dir, "session_data")
    if os.path.exists(session_dir):
        print(f"📤 Removing session data directory: {session_dir}")
        try:
            shutil.rmtree(session_dir)
            print("✅ Session data removed successfully")
        except Exception as e:
            print(f"❌ Error removing session data: {e}")
            print("Attempting to continue...")
    
    # Ensure the parent directory exists
    db_parent = Path(DB_PATH).parent
    os.makedirs(db_parent, exist_ok=True)
    
    # Recreate database
    print("\n🔧 Initializing fresh database with schema...")
    
    # Import here to avoid circular imports
    from database.db_schema import initialize_database

    try:
        initialize_database()
        print("✅ Database structure created successfully")
    except Exception as e:
        print(f"❌ Error during database schema creation: {e}")
        print("Database reset failed!")
        return False

    # Populate with initial data
    print("\n🔧 Populating database with initial data...")
    try:
        # Create database connection with foreign keys initially disabled
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # Temporarily disable foreign key constraints for data population
        conn.execute("PRAGMA foreign_keys = OFF")
        
        # Populate avatars
        print("Adding avatars...")
        avatars = [
            {"id": "cat", "name": "Whiskers the Cat", "emoji": "🐱", "color": "#ff9ff3"},
            {"id": "dog", "name": "Buddy the Dog", "emoji": "🐶", "color": "#feca57"},
            {"id": "rabbit", "name": "Hoppy the Rabbit", "emoji": "🐰", "color": "#ff6b6b"},
            {"id": "bear", "name": "Berry the Bear", "emoji": "🐻", "color": "#48dbfb"}
        ]

        cursor = conn.cursor()
        for avatar in avatars:
            cursor.execute(
                "INSERT INTO avatars (id, name, emoji, color) VALUES (?, ?, ?, ?)",
                (avatar["id"], avatar["name"], avatar["emoji"], avatar["color"])
            )
        
        # Add the Taking Turns scenario
        print("Adding scenarios...")
        cursor.execute(
            "INSERT INTO scenarios (id, title, description, image_path) VALUES (?, ?, ?, ?)",
            (
                1, 
                "Taking Turns",
                "Learn how to take turns and share toys with friends",
                "images/scenario_taking_turns.jpg"
            )
        )
        
        # Commit the changes
        conn.commit()
        
        # Re-enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Add phases for Taking Turns scenario
        print("Adding phases and options...")
        phases = [
            # Stage 1: Taking Turns with Toys
            {
                "scenario_id": 1,  # Matching the above scenario ID
                "phase_id": "toys",
                "description": "Taking Turns with Toys",
                "prompt": "Hi there! Do you like playing with toys? I love playing with toys too! If we both want to play with the same toy, what should we do?"
            },
            # Stage 2: Trading Toys
            {
                "scenario_id": 1,
                "phase_id": "trading",
                "description": "Trading Toys",
                "prompt": "If my friend is playing with a toy I like, what can I do? I can try trading a toy! That way, we both get to play with something fun!"
            },
            # Stage 3: Using a Timer for Turns
            {
                "scenario_id": 1,
                "phase_id": "timer",
                "description": "Using a Timer for Turns",
                "prompt": "Sometimes, when we want to play with a toy, someone else is already using it. What can we do? We can use a timer so everyone gets a turn! Do you think that's fair?"
            },
            # Stage 4: Waiting for My Turn
            {
                "scenario_id": 1,
                "phase_id": "waiting",
                "description": "Waiting for My Turn",
                "prompt": "Sometimes, our friend isn't ready to share yet, and that's okay! What should we do while we wait?"
            },
            # Stage 5: Asking an Adult for Help
            {
                "scenario_id": 1,
                "phase_id": "adult_help",
                "description": "Asking an Adult for Help",
                "prompt": "If we don't know what to do, we can always ask an adult for help! That way, everything feels fair for everyone."
            },
            # Stage 6: Celebrating Good Choices
            {
                "scenario_id": 1,
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
            cursor.execute(
                "SELECT id FROM phases WHERE scenario_id = ? AND phase_id = ?", 
                (phase["scenario_id"], phase["phase_id"])
            )
            phase_db_id = cursor.fetchone()[0]
            
            # Add options for each phase
            options = []
            feedback = []
            
            if phase["phase_id"] == "toys":
                options = [
                    {
                        "phase_id": phase_db_id,
                        "option_id": "a",
                        "text": "Take the toy from a friend.",
                        "icon": "😬",
                        "emotion": "negative",
                        "next_phase": "trading"
                    },
                    {
                        "phase_id": phase_db_id,
                        "option_id": "b",
                        "text": "Politely ask, 'Can I have a turn, please?'",
                        "icon": "😊",
                        "emotion": "positive",
                        "next_phase": "trading"
                    },
                    {
                        "phase_id": phase_db_id,
                        "option_id": "c",
                        "text": "Walk away without saying anything.",
                        "icon": "😕",
                        "emotion": "neutral",
                        "next_phase": "trading"
                    }
                ]
                
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
                        "text": "Wow! Great job! Asking nicely makes our friends happy and more willing to share.",
                        "positive": True,
                        "guidance": False
                    },
                    {
                        "phase_id": phase_db_id,
                        "option_id": "c",
                        "text": "Hmm, walking away is okay, but if you really want to play, you can try asking first!",
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
                        "text": "I understand, you really want that toy. But how about we ask if they want to trade?",
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
                        "text": "Hmm, asking too much might make our friend feel stressed. Let's try using a timer!",
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
                        "text": "Waiting can be tough, but there are so many fun things to do! Let's ask our friend when they'll be done!",
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
        
        # Commit all changes
        conn.commit()
        print("✅ Initial data populated successfully")
        
    except Exception as e:
        print(f"❌ Error during data population: {e}")
        print("Database reset incomplete!")
        # Continue anyway to finish cleanup
        if 'conn' in locals():
            conn.close()
        return False
    
    finally:
        # Make sure connection is closed
        if 'conn' in locals():
            conn.close()

    print("\n✅ Database reset complete!")
    print(f"📊 New database created at: {os.path.abspath(DB_PATH)}")
    return True


if __name__ == "__main__":
    # Check for force flag
    force = len(sys.argv) > 1 and sys.argv[1] in ['-f', '--force']
    success = reset_database(force)
    sys.exit(0 if success else 1)