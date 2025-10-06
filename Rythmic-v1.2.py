import time
import getpass
import statistics
import json
import os
from collections import defaultdict


class KeystrokeAuthenticator:
    def __init__(self, profile_file='keystroke_profile.json'):
        self.profile_file = profile_file
        self.profiles = self.load_profiles()

    def load_profiles(self):
        """Load existing keystroke profiles from file"""
        if os.path.exists(self.profile_file):
            with open(self.profile_file, 'r') as f:
                return json.load(f)
        return {}

    def save_profiles(self):
        """Save keystroke profiles to file"""
        with open(self.profile_file, 'w') as f:
            json.dump(self.profiles, f, indent=2)

    @staticmethod
    def capture_keystroke_timing(prompt="Enter password: "):
        """Capture password with keystroke timing data"""
        print(prompt, end='', flush=True)
        password = ""
        timings = []
        last_time = time.perf_counter()

        # Platform-specific keystroke capture
        try:
            import msvcrt  # Windows
            while True:
                if msvcrt.kbhit():
                    char = msvcrt.getch()
                    current_time = time.perf_counter()

                    if char == b'\r':  # Enter key
                        break
                    elif char == b'\x08':  # Backspace
                        if password:
                            password = password[:-1]
                            timings = timings[:-1]
                            print('\b \b', end='', flush=True)
                    else:
                        try:
                            decoded_char = char.decode('utf-8')
                            password += decoded_char
                            interval = current_time - last_time
                            timings.append(interval)
                            print('*', end='', flush=True)
                            last_time = current_time
                        except:
                            pass
        except ImportError:
            # Unix/Linux/Mac fallback - uses getch-like behavior
            import sys
            import tty
            import termios

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                while True:
                    char = sys.stdin.read(1)
                    current_time = time.perf_counter()

                    if char == '\r' or char == '\n':
                        break
                    elif char == '\x7f':  # Backspace
                        if password:
                            password = password[:-1]
                            timings = timings[:-1]
                            print('\b \b', end='', flush=True)
                    elif char == '\x03':  # Ctrl+C
                        raise KeyboardInterrupt
                    else:
                        password += char
                        interval = current_time - last_time
                        timings.append(interval)
                        print('*', end='', flush=True)
                        last_time = current_time
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        print()  # New line after password entry
        return password, timings

    @staticmethod
    def calculate_timing_features(timings):
        """Calculate statistical features from timing data"""
        if len(timings) < 2:
            return None

        features = {
            'mean': statistics.mean(timings),
            'median': statistics.median(timings),
            'stdev': statistics.stdev(timings) if len(timings) > 1 else 0,
            'min': min(timings),
            'max': max(timings),
            'total_time': sum(timings)
        }
        return features

    @staticmethod
    def compare_timing_profiles(profile1, profile2, threshold=0.3):
        """Compare two timing profiles and return similarity score"""
        if not profile1 or not profile2:
            return 0

        # Calculate percentage differences for each metric
        diffs = []
        weights = {'mean': 0.3, 'median': 0.2, 'stdev': 0.2, 'total_time': 0.3}

        for key in weights:
            if profile1[key] == 0 and profile2[key] == 0:
                diffs.append(0)
            elif profile1[key] == 0 or profile2[key] == 0:
                diffs.append(1)
            else:
                diff = abs(profile1[key] - profile2[key]) / max(profile1[key], profile2[key])
                diffs.append(diff * weights[key])

        total_diff = sum(diffs)
        similarity = 1 - total_diff

        return max(0, similarity)

    def enroll_user(self, username, num_samples=3):
        """Enroll a new user by collecting multiple password samples"""
        print(f"\n=== Enrolling User: {username} ===")
        print(f"You will be asked to enter your password {num_samples} times.")
        print("Type naturally and consistently for best results.\n")

        password = None
        all_timings = []

        for i in range(num_samples):
            pwd, timings = self.capture_keystroke_timing(f"Sample {i + 1}/{num_samples}: ")

            if password is None:
                password = pwd
            elif pwd != password:
                print("❌ Password mismatch! Please start over.")
                return False

            all_timings.append(timings)
            time.sleep(0.5)

        # Calculate average profile
        avg_features = {}
        feature_keys = ['mean', 'median', 'stdev', 'min', 'max', 'total_time']

        for key in feature_keys:
            values = []
            for timings in all_timings:
                features = self.calculate_timing_features(timings)
                if features:
                    values.append(features[key])
            if values:
                avg_features[key] = statistics.mean(values)

        # Store profile
        self.profiles[username] = {
            'password': password,  # In production, hash this!
            'timing_profile': avg_features,
            'password_length': len(password)
        }

        self.save_profiles()
        print(f"✅ User '{username}' enrolled successfully!")
        return True

    def authenticate_user(self, username):
        """Authenticate a user based on password and keystroke dynamics"""
        if username not in self.profiles:
            print(f"❌ User '{username}' not found.")
            return False

        print(f"\n=== Authenticating User: {username} ===")
        password, timings = self.capture_keystroke_timing()

        profile = self.profiles[username]

        # Check password
        if password != profile['password']:
            print("❌ Authentication failed: Incorrect password")
            return False

        # Check keystroke dynamics
        current_features = self.calculate_timing_features(timings)
        if not current_features:
            print("❌ Authentication failed: Insufficient timing data")
            return False

        similarity = self.compare_timing_profiles(
            profile['timing_profile'],
            current_features
        )

        print(f"\n📊 Keystroke Pattern Similarity: {similarity * 100:.1f}%")

        # Require 60% similarity for authentication
        if similarity >= 0.60:
            print("✅ Authentication successful!")
            print(f"   Password: Correct ✓")
            print(f"   Typing Pattern: Verified ✓")
            return True
        else:
            print("❌ Authentication failed: Typing pattern mismatch")
            print("   Password was correct, but typing rhythm differs from profile.")
            return False

    def delete_user(self, username):
        """Delete a user profile"""
        if username in self.profiles:
            del self.profiles[username]
            self.save_profiles()
            print(f"✅ User '{username}' deleted.")
        else:
            print(f"❌ User '{username}' not found.")

    def list_users(self):
        """List all enrolled users"""
        if not self.profiles:
            print("No users enrolled.")
        else:
            print("\n📋 Enrolled Users:")
            for username in self.profiles:
                print(f"   - {username}")


def main():
    auth = KeystrokeAuthenticator()

    while True:
        print("\n" + "=" * 50)
        print("🔐 Keystroke Dynamics Authentication System")
        print("=" * 50)
        print("1. Enroll new user")
        print("2. Authenticate user")
        print("3. List users")
        print("4. Delete user")
        print("5. Exit")
        print()

        choice = input("Select option (1-5): ").strip()

        if choice == '1':
            username = input("Enter username: ").strip()
            if username:
                auth.enroll_user(username)
            else:
                print("❌ Username cannot be empty.")

        elif choice == '2':
            username = input("Enter username: ").strip()
            if username:
                auth.authenticate_user(username)
            else:
                print("❌ Username cannot be empty.")

        elif choice == '3':
            auth.list_users()

        elif choice == '4':
            username = input("Enter username to delete: ").strip()
            if username:
                auth.delete_user(username)
            else:
                print("❌ Username cannot be empty.")

        elif choice == '5':
            print("\n👋 Goodbye!")
            break

        else:
            print("❌ Invalid option. Please select 1-5.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Program interrupted. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
