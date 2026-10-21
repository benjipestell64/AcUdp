import time
import sys

# Function to update the status light using simple text characters
def update_status_light(state):
    # Move cursor back to the start of the line and print the status
    sys.stdout.write(f"\rStatus: [{state}]")
    sys.stdout.flush()

# Status cycle with different characters
update_status_light("● RED   ")     # Red light (or just use "R")
time.sleep(1)
update_status_light("● YELLOW")    # Yellow light (or just use "Y")
time.sleep(1)
update_status_light("● GREEN ")    # Green light (or just use "G")
time.sleep(1)

# Move to a new line after the status light
print("\nStatus cycle complete.")
