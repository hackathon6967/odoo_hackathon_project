import os
import sys

summary_text = (
    "Eco Sphere final enhancements have been successfully completed. "
    "The styling has been fully upgraded to a modern dark and light theme system with CSS variables. "
    "The overlapping fields on the login page have been aligned and fixed. "
    "The administrative dashboard and security enforcements for settings are fully functional. "
    "The database has been seeded with rich, varied department-level metrics, and ESG score recomputations are completed. "
    "Finally, the codebase has been pushed to the remote repository."
)

print("🔊 Speaking status summary...")
print(summary_text)

if sys.platform == "darwin":
    # macOS native speech command
    # Using clean formatting for the shell command
    os.system(f'say "{summary_text}"')
elif sys.platform.startswith("win"):
    # Windows native speech via SAPI.SpVoice
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Speak(summary_text)
    except ImportError:
        print("Please install pywin32 via 'pip install pywin32' to speak on Windows.")
else:
    # Linux generic speech command (espeak)
    os.system(f'espeak "{summary_text}"')

print("✅ Done!")
